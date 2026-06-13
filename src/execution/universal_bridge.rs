use std::error::Error;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;

/// Deep Dive: Universal FIX Protocol Bridge
/// Connects to Institutional Brokers (IBKR, CME, LMAX) over raw TCP using FIX 4.4 / 5.0
pub struct FixBridge {
    pub host: String,
    pub port: u16,
    pub sender_comp_id: String,
    pub target_comp_id: String,
    pub msg_seq_num: u64,
}

impl FixBridge {
    pub fn new(host: &str, port: u16, sender: &str, target: &str) -> Self {
        FixBridge {
            host: host.to_string(),
            port,
            sender_comp_id: sender.to_string(),
            target_comp_id: target.to_string(),
            msg_seq_num: 1,
        }
    }

    /// Constructs a standard FIX header and calculates the checksum
    fn construct_message(&mut self, msg_type: &str, body: &str) -> String {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_millis();
        // Time format: YYYYMMDD-HH:MM:SS.mmm (simplified for stub)
        let sending_time = format!("{}", now);

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

        println!("[FIX_BRIDGE] Sending Logon: {}", msg.replace("\x01", "|"));
        stream.write_all(msg.as_bytes()).await?;

        let mut buffer = [0; 1024];
        let n = stream.read(&mut buffer).await?;
        let response = String::from_utf8_lossy(&buffer[..n]);
        println!("[FIX_BRIDGE] Received: {}", response.replace("\x01", "|"));

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
            side,
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_millis(),
            qty,
            price
        );

        let msg = self.construct_message("D", &body);
        println!(
            "[FIX_BRIDGE] Submitting Order: {}",
            msg.replace("\x01", "|")
        );
        // In reality, we'd write this to the TcpStream
        Ok(())
    }
}
