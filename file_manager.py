# file_manager.py
import os
import shutil
import hashlib # Để tính toán hash cho việc tìm tệp trùng lặp
import datetime
import ctypes # Để lấy thông tin ổ đĩa trên Windows

from utils import get_file_details # Import hàm tiện ích

class FileManager:
    """
    Lớp này xử lý tất cả các thao tác liên quan đến hệ thống tệp.
    Cung cấp các hàm với xử lý lỗi chi tiết hơn.
    """
    def __init__(self):
        self.current_path = os.path.expanduser("~") # Bắt đầu từ thư mục người dùng

    def list_directory(self, path="."):
        """
        Liệt kê nội dung của một thư mục.
        Trả về tuple (list_of_items, error_message).
        list_of_items là danh sách các dict chứa thông tin tệp/thư mục.
        """
        target_path = path if os.path.isabs(path) else os.path.join(self.current_path, path)
        
        if not os.path.exists(target_path):
            return [], f"Lỗi: Đường dẫn không tồn tại: '{target_path}'"
        if not os.path.isdir(target_path):
            return [], f"Lỗi: Đường dẫn không phải là thư mục: '{target_path}'"

        try:
            # Kiểm tra quyền đọc thư mục
            if not os.access(target_path, os.R_OK):
                return [], f"Lỗi quyền truy cập: Không có quyền đọc thư mục '{target_path}'."
        except Exception as e:
            return [], f"Lỗi kiểm tra quyền truy cập: {e}"

        self.current_path = target_path # Cập nhật đường dẫn hiện tại

        items = []
        try:
            # Sử dụng os.scandir để hiệu quả hơn os.listdir cho các thư mục lớn
            with os.scandir(target_path) as entries:
                for entry in entries:
                    details = get_file_details(entry.path)
                    if details:
                        items.append(details)
            # Sắp xếp thư mục lên đầu, sau đó theo tên
            items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return items, None
        except PermissionError:
            return [], f"Lỗi quyền truy cập: Không thể liệt kê nội dung thư mục '{target_path}'."
        except Exception as e:
            return [], f"Lỗi khi liệt kê thư mục '{target_path}': {e}"

    def go_up(self):
        """
        Di chuyển lên một cấp thư mục.
        Trả về đường dẫn mới.
        """
        parent_path = os.path.dirname(self.current_path)
        if parent_path != self.current_path: # Đảm bảo không đi quá thư mục gốc của ổ đĩa
            self.current_path = parent_path
        return self.current_path

    def change_directory(self, path):
        """
        Thay đổi thư mục hiện tại.
        Trả về tuple (success, message).
        """
        full_path = path if os.path.isabs(path) else os.path.join(self.current_path, path)
        if os.path.isdir(full_path):
            if os.access(full_path, os.R_OK):
                self.current_path = full_path
                return True, None
            else:
                return False, f"Lỗi quyền truy cập: Không có quyền đọc thư mục '{full_path}'."
        return False, f"Đường dẫn không hợp lệ hoặc không tồn tại: '{full_path}'."

    def copy_item(self, source, destination_dir):
        """
        Sao chép tệp hoặc thư mục.
        Trả về tuple (success, message).
        """
        if not os.path.exists(source):
            return False, f"Nguồn không tồn tại: '{source}'"
        if not os.path.isdir(destination_dir):
            return False, f"Thư mục đích không hợp lệ: '{destination_dir}'"
        if not os.access(destination_dir, os.W_OK):
            return False, f"Lỗi quyền truy cập: Không có quyền ghi vào thư mục đích '{destination_dir}'."

        dest_path = os.path.join(destination_dir, os.path.basename(source))
        try:
            if os.path.isdir(source):
                shutil.copytree(source, dest_path)
            else:
                shutil.copy2(source, dest_path)
            return True, None
        except FileExistsError:
            return False, f"Mục '{os.path.basename(source)}' đã tồn tại tại đích. Vui lòng xóa hoặc đổi tên."
        except PermissionError:
            return False, f"Lỗi quyền truy cập khi sao chép '{source}'."
        except Exception as e:
            return False, f"Lỗi khi sao chép '{source}' đến '{destination_dir}': {e}"

    def move_item(self, source, destination_dir):
        """
        Di chuyển tệp hoặc thư mục.
        Trả về tuple (success, message).
        """
        if not os.path.exists(source):
            return False, f"Nguồn không tồn tại: '{source}'"
        if not os.path.isdir(destination_dir):
            return False, f"Thư mục đích không hợp lệ: '{destination_dir}'"
        if not os.access(destination_dir, os.W_OK):
            return False, f"Lỗi quyền truy cập: Không có quyền ghi vào thư mục đích '{destination_dir}'."
        if not os.access(os.path.dirname(source), os.W_OK):
            return False, f"Lỗi quyền truy cập: Không có quyền xóa mục gốc '{source}'."

        dest_path = os.path.join(destination_dir, os.path.basename(source))
        try:
            shutil.move(source, dest_path)
            return True, None
        except shutil.Error as e: # shutil.Error cho các lỗi di chuyển cụ thể
            return False, f"Lỗi di chuyển: {e}. Có thể mục đang được sử dụng hoặc quyền truy cập."
        except PermissionError:
            return False, f"Lỗi quyền truy cập khi di chuyển '{source}'."
        except Exception as e:
            return False, f"Lỗi khi di chuyển '{source}' đến '{destination_dir}': {e}"

    def delete_item(self, path):
        """
        Xóa tệp hoặc thư mục.
        Cần cẩn thận khi sử dụng hàm này với quyền admin.
        Trả về tuple (success, message).
        """
        if not os.path.exists(path):
            return False, f"Mục không tồn tại: '{path}'"
        if not os.access(path, os.W_OK): # Cần quyền ghi để xóa
            return False, f"Lỗi quyền truy cập: Không có quyền xóa '{path}'."

        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True, None
        except PermissionError:
            return False, f"Lỗi quyền truy cập khi xóa '{path}'. Mục có thể đang được sử dụng."
        except OSError as e: # Ví dụ: thư mục không trống
            return False, f"Lỗi hệ thống khi xóa '{path}': {e}"
        except Exception as e:
            return False, f"Lỗi khi xóa '{path}': {e}"

    def create_folder(self, parent_dir, folder_name):
        """
        Tạo một thư mục mới.
        Trả về tuple (success, message).
        """
        new_path = os.path.join(parent_dir, folder_name)
        if not os.access(parent_dir, os.W_OK):
            return False, f"Lỗi quyền truy cập: Không có quyền tạo thư mục trong '{parent_dir}'."
        try:
            os.makedirs(new_path)
            return True, None
        except FileExistsError:
            return False, f"Thư mục '{folder_name}' đã tồn tại."
        except PermissionError:
            return False, f"Lỗi quyền truy cập khi tạo thư mục '{new_path}'."
        except Exception as e:
            return False, f"Lỗi khi tạo thư mục '{new_path}': {e}"

    def rename_item(self, old_path, new_name):
        """
        Đổi tên tệp hoặc thư mục.
        Trả về tuple (success, message).
        """
        if not os.path.exists(old_path):
            return False, f"Mục không tồn tại: '{old_path}'"
        if not os.access(os.path.dirname(old_path), os.W_OK):
            return False, f"Lỗi quyền truy cập: Không có quyền đổi tên trong thư mục gốc của '{old_path}'."

        new_path = os.path.join(os.path.dirname(old_path), new_name)
        if os.path.exists(new_path):
            return False, f"Tên '{new_name}' đã tồn tại trong thư mục này."
        try:
            os.rename(old_path, new_path)
            return True, None
        except PermissionError:
            return False, f"Lỗi quyền truy cập khi đổi tên '{old_path}'. Mục có thể đang được sử dụng."
        except Exception as e:
            return False, f"Lỗi khi đổi tên '{old_path}' thành '{new_name}': {e}"

    def search_files(self, root_dir, keyword, search_type="name", case_sensitive=False, min_size_mb=0, max_size_mb=0, days_old=0):
        """
        Tìm kiếm tệp hoặc thư mục theo nhiều tiêu chí.
        root_dir: Thư mục gốc để bắt đầu tìm kiếm.
        keyword: Từ khóa tìm kiếm.
        search_type: "name", "content", "extension".
        case_sensitive: True/False.
        min_size_mb: Kích thước tối thiểu (MB).
        max_size_mb: Kích thước tối đa (MB).
        days_old: Tìm các tệp cũ hơn số ngày này (dựa trên thời gian sửa đổi).
        Trả về danh sách các dict chứa thông tin tệp/thư mục.
        """
        results = []
        keyword_search = keyword if case_sensitive else keyword.lower()
        
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Bỏ qua các thư mục không có quyền truy cập
            try:
                # Kiểm tra quyền đọc thư mục hiện tại trước khi duyệt
                if not os.access(dirpath, os.R_OK):
                    # print(f"Bỏ qua thư mục không có quyền truy cập: {dirpath}")
                    continue
            except Exception:
                continue # Nếu có lỗi khi kiểm tra quyền, bỏ qua

            for name in filenames + dirnames: # Tìm kiếm cả tệp và thư mục
                full_path = os.path.join(dirpath, name)
                
                # Bỏ qua nếu không tồn tại (có thể bị xóa trong quá trình quét)
                if not os.path.exists(full_path):
                    continue

                item_details = get_file_details(full_path)
                if not item_details:
                    continue

                # Kiểm tra theo tên/mở rộng
                name_to_check = name if case_sensitive else name.lower()
                
                name_match = False
                if search_type == "name" and keyword_search in name_to_check:
                    name_match = True
                elif search_type == "extension":
                    _, ext = os.path.splitext(name_to_check)
                    if keyword_search == ext or (keyword_search.startswith('.') and keyword_search == ext):
                        name_match = True
                
                if not name_match and search_type != "content":
                    continue # Nếu không khớp tên/mở rộng và không tìm kiếm nội dung, bỏ qua

                # Kiểm tra kích thước
                size_match = True
                if not item_details['is_dir']: # Chỉ kiểm tra kích thước cho tệp
                    if min_size_mb > 0 and item_details['size'] < min_size_mb * 1024 * 1024:
                        size_match = False
                    if max_size_mb > 0 and item_details['size'] > max_size_mb * 1024 * 1024:
                        size_match = False
                
                if not size_match:
                    continue

                # Kiểm tra ngày sửa đổi
                date_match = True
                if days_old > 0 and not item_details['is_dir']: # Chỉ kiểm tra ngày cho tệp
                    try:
                        modified_timestamp = os.path.getmtime(full_path)
                        current_timestamp = datetime.datetime.now().timestamp()
                        diff_seconds = current_timestamp - modified_timestamp
                        diff_days = diff_seconds / (24 * 3600)
                        if diff_days < days_old:
                            date_match = False
                    except Exception:
                        date_match = False # Lỗi khi lấy thời gian, coi như không khớp
                
                if not date_match:
                    continue

                # Kiểm tra nội dung (chỉ cho tệp văn bản)
                content_match = True
                if search_type == "content" and not item_details['is_dir']:
                    if name.lower().endswith(('.txt', '.log', '.csv', '.json', '.xml', '.py', '.html', '.css', '.js')):
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                file_content = f.read()
                                if not case_sensitive:
                                    file_content = file_content.lower()
                                if keyword_search not in file_content:
                                    content_match = False
                        except Exception:
                            content_match = False # Bỏ qua các tệp không đọc được hoặc có lỗi mã hóa
                    else:
                        content_match = False # Không phải tệp văn bản để tìm kiếm nội dung

                if (search_type != "content" and name_match and size_match and date_match) or \
                   (search_type == "content" and content_match and size_match and date_match):
                    results.append(item_details)
        return results

    def get_file_hash(self, file_path, hash_algorithm='md5', block_size=65536):
        """
        Tính toán hash của một tệp để kiểm tra trùng lặp.
        hash_algorithm: 'md5', 'sha1', 'sha256'.
        block_size: Kích thước khối để đọc tệp.
        """
        if not os.path.isfile(file_path):
            return None
        
        try:
            if hash_algorithm == 'md5':
                hasher = hashlib.md5()
            elif hash_algorithm == 'sha1':
                hasher = hashlib.sha1()
            elif hash_algorithm == 'sha256':
                hasher = hashlib.sha256()
            else:
                raise ValueError("Thuật toán hash không được hỗ trợ.")

            with open(file_path, 'rb') as f:
                for block in iter(lambda: f.read(block_size), b''):
                    hasher.update(block)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Lỗi khi tính toán hash cho '{file_path}': {e}")
            return None

    def get_drive_info(self, drive_path):
        """
        Lấy thông tin dung lượng ổ đĩa trên Windows.
        drive_path: Ví dụ 'C:\\'.
        Trả về tuple (total_gb, free_gb, error_message).
        """
        if os.name == 'nt': # Chỉ cho Windows
            try:
                # Sử dụng GetDiskFreeSpaceExW từ kernel32.dll
                free_bytes_available = ctypes.c_ulonglong(0)
                total_number_of_bytes = ctypes.c_ulonglong(0)
                total_number_of_free_bytes = ctypes.c_ulonglong(0)

                ret = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(drive_path),
                    ctypes.byref(free_bytes_available),
                    ctypes.byref(total_number_of_bytes),
                    ctypes.byref(total_number_of_free_bytes)
                )

                if ret:
                    total_gb = total_number_of_bytes.value / (1024**3)
                    free_gb = free_bytes_available.value / (1024**3)
                    return round(total_gb, 2), round(free_gb, 2), None
                else:
                    return 0, 0, f"Không thể lấy thông tin ổ đĩa cho '{drive_path}'. Lỗi: {ctypes.GetLastError()}"
            except Exception as e:
                return 0, 0, f"Lỗi khi lấy thông tin ổ đĩa: {e}"
        else:
            # Đối với các hệ điều hành khác, có thể sử dụng os.statvfs (chưa triển khai chi tiết)
            return 0, 0, "Tính năng này hiện chỉ hỗ trợ Windows."

