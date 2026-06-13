use chrono::Utc;
use std::error::Error;
use std::io::{Error as IoError, ErrorKind};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::time::{timeout, Duration};

/// Deep Dive: Universal FIX Protocol Bridge
/// Connects to Institutional Brokers (IBKR, CME, LMAX) over raw TCP using FIX 4.4 / 5.0
pub struct FixBridge {
    pub host: String,
    pub port: u16,
    pub sender_comp_id: String,
    pub target_comp_id: String,
    pub msg_seq_num: u64,
    stream: Option<TcpStream>,
}

impl FixBridge {
    pub fn new(host: &str, port: u16, sender: &str, target: &str) -> Self {
        FixBridge {
            host: host.to_string(),
            port,
            sender_comp_id: sender.to_string(),
            target_comp_id: target.to_string(),
            msg_seq_num: 1,
            stream: None,
        }
    }

    /// Constructs a standard FIX header and calculates the checksum
    fn construct_message(&mut self, msg_type: &str, body: &str) -> String {
        let sending_time = Utc::now().format("%Y%m%d-%H:%M:%S%.3f");

        let header = format!(
            "35={}\x0149={}\x0156={}\x0134={}\x0152={}\x01",
            msg_type, self.sender_comp_id, self.target_comp_id, self.msg_seq_num, sending_time
        );

        let unchecksummed = format!("{}{}", header, body);
        let length = unchecksummed.len();

        let msg_with_len = format!("8=FIX.4.4\x019={}\x01{}", length, unchecksummed);

        // Calculate Checksum (modulo 256 sum of all bytes)
        let mut sum: u32 = 0;
        for b in msg_with_len.as_bytes() {
            sum += *b as u32;
        }
        let checksum = sum % 256;

        let final_msg = format!("{}10={:03}\x01", msg_with_len, checksum);
        self.msg_seq_num += 1;

        final_msg
    }

    /// Logs into the FIX Session
    pub async fn logon(&mut self) -> Result<(), Box<dyn Error>> {
        let addr = format!("{}:{}", self.host, self.port);
        let mut stream = TcpStream::connect(addr).await?;

        // 35=A is Logon Message. 98=0 (No Encryption), 108=30 (Heartbeat interval 30s)
        let logon_body = "98=0\x01108=30\x01";
        let msg = self.construct_message("A", logon_body);

        stream.write_all(msg.as_bytes()).await?;

        let mut buffer = [0; 4096];
        let n = timeout(Duration::from_secs(10), stream.read(&mut buffer)).await??;
        if n == 0 {
            return Err(
                IoError::new(ErrorKind::UnexpectedEof, "FIX peer closed during logon").into(),
            );
        }
        let response = String::from_utf8_lossy(&buffer[..n]);
        if !response.contains("\x0135=A\x01") {
            return Err(IoError::new(
                ErrorKind::PermissionDenied,
                format!(
                    "FIX logon rejected or malformed: {}",
                    response.replace('\x01', "|")
                ),
            )
            .into());
        }

        self.stream = Some(stream);
        Ok(())
    }

    /// Submits a New Order Single (35=D) to the broker
    pub async fn send_order(
        &mut self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
    ) -> Result<(), Box<dyn Error>> {
        let side_code = match side.trim().to_ascii_uppercase().as_str() {
            "BUY" | "1" => "1",
            "SELL" | "2" => "2",
            _ => {
                return Err(
                    IoError::new(ErrorKind::InvalidInput, "side must be BUY or SELL").into(),
                )
            }
        };
        if symbol.is_empty()
            || symbol.bytes().any(|byte| byte == b'=' || byte == 0x01)
            || !qty.is_finite()
            || qty <= 0.0
            || !price.is_finite()
            || price <= 0.0
        {
            return Err(IoError::new(ErrorKind::InvalidInput, "invalid FIX order fields").into());
        }

        // 11=ClOrdID, 21=HandlInst(1=Auto), 55=Symbol, 54=Side(1=Buy,2=Sell), 60=TransactTime, 38=Qty, 40=OrdType(2=Limit), 44=Price
        let cl_ord_id = format!(
            "SOV-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_micros()
        );
        let body = format!(
            "11={}\x0121=1\x0155={}\x0154={}\x0160={}\x0138={}\x0140=2\x0144={}\x01",
            cl_ord_id,
            symbol,
            side_code,
            Utc::now().format("%Y%m%d-%H:%M:%S%.3f"),
            qty,
            price
        );

        let msg = self.construct_message("D", &body);
        let stream = self.stream.as_mut().ok_or_else(|| {
            IoError::new(
                ErrorKind::NotConnected,
                "FIX order blocked because session is not logged on",
            )
        })?;
        stream.write_all(msg.as_bytes()).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constructed_message_has_valid_body_length_and_checksum() {
        let mut bridge = FixBridge::new("localhost", 9876, "SENDER", "TARGET");
        let message = bridge.construct_message("0", "112=ping\x01");
        let fields: Vec<&str> = message.split('\x01').collect();
        let body_length: usize = fields[1].strip_prefix("9=").unwrap().parse().unwrap();
        let body_start = message.find("35=").unwrap();
        let checksum_start = message.rfind("10=").unwrap();

        assert_eq!(body_length, checksum_start - body_start);
        let expected_checksum: u32 = message.as_bytes()[..checksum_start]
            .iter()
            .map(|byte| *byte as u32)
            .sum::<u32>()
            % 256;
        assert_eq!(
            fields[fields.len() - 2],
            format!("10={expected_checksum:03}")
        );
    }

    #[tokio::test]
    async fn order_fails_closed_without_logged_on_session() {
        let mut bridge = FixBridge::new("localhost", 9876, "SENDER", "TARGET");

        let error = bridge
            .send_order("SPY", "BUY", 1.0, 100.0)
            .await
            .unwrap_err();

        assert_eq!(
            error.downcast_ref::<IoError>().unwrap().kind(),
            ErrorKind::NotConnected
        );
    }

    #[tokio::test]
    async fn invalid_order_is_rejected_before_transport() {
        let mut bridge = FixBridge::new("localhost", 9876, "SENDER", "TARGET");

        assert!(bridge.send_order("SPY", "HOLD", 1.0, 100.0).await.is_err());
        assert!(bridge
            .send_order("SPY", "BUY", f64::NAN, 100.0)
            .await
            .is_err());
        assert!(bridge
            .send_order("BAD\x01SYMBOL", "BUY", 1.0, 100.0)
            .await
            .is_err());
    }
}
