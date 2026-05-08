// libvma / onload kernel bypass implementation
extern "C" {
    fn onload_zc_recv(fd: i32, msg: *mut u8) -> i32;
}

pub fn bypass_recv(socket_fd: i32) {
    let mut buf = [0u8; 1500];
    unsafe {
        onload_zc_recv(socket_fd, buf.as_mut_ptr());
    }
}
