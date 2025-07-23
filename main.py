# main.py
import sys
import os
import subprocess
import ctypes

# Import lớp ứng dụng chính từ hse_app
from hse_app import HSEApp

def is_admin():
    """
    Kiểm tra xem ứng dụng có đang chạy với quyền Administrator hay không.
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """
    Khởi chạy lại script với quyền Administrator.
    """
    if sys.version_info[0] == 3:
        # Python 3
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    else:
        # Python 2 (không khuyến khích sử dụng)
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)

def main():
    """
    Hàm chính để khởi động ứng dụng.
    """
    if not is_admin():
        print("Hurican Smart Explorer yêu cầu quyền Administrator để hoạt động đầy đủ.")
        run_as_admin()
        sys.exit(0) # Thoát tiến trình hiện tại sau khi yêu cầu quyền admin
    else:
        print("Hurican Smart Explorer đang chạy với quyền Administrator.")
        # Khởi tạo và chạy ứng dụng HSE
        app = HSEApp()
        app.mainloop()

if __name__ == "__main__":
    main()

