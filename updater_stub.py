# updater_stub.py
import sys
import os
import time
import shutil
import subprocess

def run_updater():
    """
    Chạy quá trình cập nhật.
    Updater này sẽ được khởi chạy bởi ứng dụng chính.
    Nó sẽ đợi ứng dụng chính thoát, sau đó thay thế tệp EXE cũ bằng tệp EXE mới và khởi chạy lại.
    """
    if len(sys.argv) != 4:
        # Cần 3 đối số: đường dẫn của updater_stub.exe, đường dẫn của old_app_exe, đường dẫn của new_app_exe
        print("Usage: updater_stub.exe <old_app_exe_path> <new_app_exe_path> <updater_stub_exe_path>")
        sys.exit(1)

    old_app_exe_path = sys.argv[1] # Đường dẫn của HSE.exe hiện tại đang chạy
    new_app_exe_path = sys.argv[2] # Đường dẫn của HSE.exe mới đã tải về
    updater_stub_exe_path = sys.argv[3] # Đường dẫn của updater_stub.exe này

    print(f"Updater Stub: Starting update process...")
    print(f"Updater Stub: Old app path: {old_app_exe_path}")
    print(f"Updater Stub: New app path: {new_app_exe_path}")
    print(f"Updater Stub: Updater stub path: {updater_stub_exe_path}")

    # Đợi ứng dụng chính thoát hoàn toàn
    # Kiểm tra xem tệp EXE cũ còn bị khóa không
    max_retries = 30
    retry_delay = 1 # giây
    for i in range(max_retries):
        try:
            # Thử mở tệp để ghi, nếu thành công nghĩa là tệp không còn bị khóa
            with open(old_app_exe_path, 'a'):
                pass
            print(f"Updater Stub: Old app ({old_app_exe_path}) is no longer in use.")
            break
        except IOError:
            print(f"Updater Stub: Old app still in use, retrying in {retry_delay}s... ({i+1}/{max_retries})")
            time.sleep(retry_delay)
    else:
        print("Updater Stub: Failed to get access to old app. Aborting update.")
        sys.exit(1) # Không thể truy cập tệp, thoát

    try:
        # 1. Xóa tệp EXE cũ (hoặc đổi tên để dự phòng)
        if os.path.exists(old_app_exe_path):
            backup_path = old_app_exe_path + ".old"
            if os.path.exists(backup_path):
                os.remove(backup_path) # Xóa bản sao lưu cũ nếu có
            os.rename(old_app_exe_path, backup_path)
            print(f"Updater Stub: Backed up old app to {backup_path}")
        
        # 2. Di chuyển tệp EXE mới vào vị trí của tệp cũ
        shutil.move(new_app_exe_path, old_app_exe_path)
        print(f"Updater Stub: Moved new app to {old_app_exe_path}")

        # 3. Khởi chạy lại ứng dụng đã cập nhật
        print(f"Updater Stub: Launching updated app: {old_app_exe_path}")
        subprocess.Popen([old_app_exe_path]) # Khởi chạy mà không đợi

        # 4. Dọn dẹp updater stub và bản sao lưu
        print("Updater Stub: Cleaning up...")
        # Đợi một chút để ứng dụng mới kịp khởi chạy trước khi tự xóa
        time.sleep(2) 
        if os.path.exists(backup_path):
            os.remove(backup_path)
            print(f"Updater Stub: Removed backup {backup_path}")
        if os.path.exists(updater_stub_exe_path):
            os.remove(updater_stub_exe_path)
            print(f"Updater Stub: Removed updater stub {updater_stub_exe_path}")

        print("Updater Stub: Update complete and cleaned up. Exiting.")
        sys.exit(0)

    except Exception as e:
        print(f"Updater Stub: An error occurred during update: {e}")
        # Quan trọng: Nếu có lỗi, không tự xóa updater stub để có thể gỡ lỗi
        sys.exit(1)

if __name__ == "__main__":
    run_updater()
