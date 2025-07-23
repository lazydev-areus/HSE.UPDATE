# smart_features.py
import os
import json
import datetime
from collections import defaultdict
from utils import get_file_details
from file_manager import FileManager # Để sử dụng get_file_hash

class SmartFeatures:
    """
    Lớp này chứa các thuật toán "thông minh" không sử dụng ML/AI.
    Cung cấp các tính năng như tìm tệp trùng lặp, tệp lớn/cũ, gợi ý ngữ cảnh.
    """
    def __init__(self, history_file="hse_history.json"):
        self.history_file = history_file
        self.recent_files = [] # Danh sách các tệp/thư mục gần đây (đường dẫn)
        self.frequent_items = defaultdict(int) # Đếm tần suất truy cập (đường dẫn -> số lần)
        self.file_manager = FileManager() # Khởi tạo FileManager để dùng các hàm của nó
        self._load_history()

    def _load_history(self):
        """
        Tải lịch sử từ tệp JSON.
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Lọc bỏ các đường dẫn không còn tồn tại
                    self.recent_files = [p for p in data.get('recent_files', []) if os.path.exists(p)]
                    self.frequent_items = defaultdict(int, {p: count for p, count in data.get('frequent_items', {}).items() if os.path.exists(p)})
            except json.JSONDecodeError:
                print("Lỗi đọc lịch sử tệp JSON. Tạo lịch sử mới.")
            except Exception as e:
                print(f"Lỗi khi tải lịch sử: {e}")

    def _save_history(self):
        """
        Lưu lịch sử vào tệp JSON.
        """
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'recent_files': self.recent_files,
                    'frequent_items': dict(self.frequent_items)
                }, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Lỗi khi lưu lịch sử: {e}")

    def track_access(self, path):
        """
        Theo dõi quyền truy cập vào một tệp/thư mục.
        """
        if not os.path.exists(path): # Không theo dõi nếu tệp/thư mục không tồn tại
            return

        # Cập nhật danh sách gần đây
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path) # Thêm vào đầu danh sách
        self.recent_files = self.recent_files[:50] # Giới hạn 50 mục gần đây

        # Cập nhật tần suất truy cập
        self.frequent_items[path] += 1
        self._save_history()

    def get_recent_items(self):
        """
        Trả về danh sách các tệp/thư mục gần đây.
        Kiểm tra sự tồn tại của tệp/thư mục trước khi trả về.
        """
        valid_recent_items = []
        # Lọc bỏ các mục không còn tồn tại và lấy chi tiết
        self.recent_files = [p for p in self.recent_files if os.path.exists(p)]
        for path in self.recent_files:
            details = get_file_details(path)
            if details:
                valid_recent_items.append(details)
        return valid_recent_items

    def get_frequent_items(self, limit=20):
        """
        Trả về các tệp/thư mục được truy cập thường xuyên nhất.
        """
        # Lọc bỏ các mục không còn tồn tại trước khi sắp xếp
        self.frequent_items = defaultdict(int, {p: count for p, count in self.frequent_items.items() if os.path.exists(p)})
        sorted_items = sorted(self.frequent_items.items(), key=lambda item: item[1], reverse=True)
        frequent_items_details = []
        for path, count in sorted_items:
            details = get_file_details(path)
            if details:
                frequent_items_details.append(details)
            if len(frequent_items_details) >= limit:
                break
        return frequent_items_details

    def categorize_files(self, file_list):
        """
        Phân loại các tệp dựa trên phần mở rộng và ngữ cảnh.
        """
        categories = defaultdict(list)
        for item in file_list:
            if item['is_dir']:
                categories['Thư mục'].append(item)
            else:
                _, ext = os.path.splitext(item['name'])
                ext = ext.lower()
                if ext in [".txt", ".doc", ".docx", ".pdf", ".odt", ".rtf", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"]:
                    categories['Tài liệu'].append(item)
                elif ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico", ".webp"]:
                    categories['Hình ảnh'].append(item)
                elif ext in [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"]:
                    categories['Âm thanh'].append(item)
                elif ext in [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"]:
                    categories['Video'].append(item)
                elif ext in [".zip", ".rar", ".7z", ".tar.gz", ".gz", ".iso"]:
                    categories['Lưu trữ & ISO'].append(item)
                elif ext in [".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".dll", ".sys"]:
                    categories['Thực thi & Hệ thống'].append(item)
                elif ext in [".py", ".js", ".html", ".css", ".json", ".xml", ".java", ".c", ".cpp", ".cs", ".php", ".go", ".rb", ".swift"]:
                    categories['Mã nguồn & Cấu hình'].append(item)
                elif ext in [".log", ".tmp", ".bak"]:
                    categories['Tệp tạm & Nhật ký'].append(item)
                else:
                    categories['Khác'].append(item)
        return categories

    def get_contextual_suggestions(self, current_path, limit=10):
        """
        Đưa ra gợi ý dựa trên ngữ cảnh (ví dụ: các thư mục con thường xuyên truy cập
        trong thư mục hiện tại, các tệp liên quan, hoặc các thư mục "anh em" thường xuyên).
        """
        suggestions = []
        
        # 1. Gợi ý các thư mục con thường xuyên truy cập trong đường dẫn hiện tại
        for path, count in self.frequent_items.items():
            if os.path.isdir(path) and os.path.dirname(path) == current_path:
                suggestions.append(get_file_details(path))

        # 2. Gợi ý các tệp cùng loại (phần mở rộng) được truy cập gần đây trong thư mục hiện tại
        current_dir_files = [item for item in self.get_recent_items() if os.path.dirname(item['path']) == current_path and not item['is_dir']]
        if current_dir_files:
            # Lấy phần mở rộng phổ biến nhất trong thư mục hiện tại từ các tệp gần đây
            ext_counts = defaultdict(int)
            for item in current_dir_files:
                _, ext = os.path.splitext(item['name'])
                ext_counts[ext.lower()] += 1
            
            if ext_counts:
                most_common_ext = max(ext_counts, key=ext_counts.get)
                # Tìm các tệp khác trong thư mục hiện tại có cùng phần mở rộng
                current_dir_items, _ = self.file_manager.list_directory(current_path)
                for item in current_dir_items:
                    if not item['is_dir'] and os.path.splitext(item['name'])[1].lower() == most_common_ext and item not in suggestions:
                        suggestions.append(item)

        # 3. Gợi ý các thư mục "anh em" (sibling directories) thường xuyên truy cập
        parent_of_current = os.path.dirname(current_path)
        if parent_of_current and parent_of_current != current_path:
            for path, count in self.frequent_items.items():
                if os.path.isdir(path) and os.path.dirname(path) == parent_of_current and path != current_path:
                    suggestions.append(get_file_details(path))

        # Loại bỏ các mục trùng lặp và sắp xếp theo tần suất (nếu có trong frequent_items)
        unique_suggestions = {item['path']: item for item in suggestions}.values()
        sorted_suggestions = sorted(list(unique_suggestions), key=lambda x: self.frequent_items.get(x['path'], 0), reverse=True)
        
        return sorted_suggestions[:limit]

    def find_duplicate_files(self, root_dir, hash_algorithm='md5', min_size_mb=1):
        """
        Tìm các tệp trùng lặp trong một thư mục gốc dựa trên kích thước và hash nội dung.
        min_size_mb: Chỉ xem xét các tệp lớn hơn kích thước này để tăng hiệu suất.
        Trả về dictionary: {hash_value: [file_path1, file_path2, ...]}
        """
        files_by_size = defaultdict(list)
        duplicate_hashes = {}
        min_size_bytes = min_size_mb * 1024 * 1024

        print(f"Bắt đầu tìm kiếm tệp trùng lặp trong '{root_dir}'...")

        for dirpath, _, filenames in os.walk(root_dir):
            try:
                if not os.access(dirpath, os.R_OK):
                    continue
            except Exception:
                continue

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        if file_size >= min_size_bytes:
                            files_by_size[file_size].append(file_path)
                except Exception:
                    continue # Bỏ qua các tệp không thể truy cập

        # Chỉ xem xét các nhóm tệp có cùng kích thước và có nhiều hơn 1 tệp
        for size, file_paths in files_by_size.items():
            if len(file_paths) > 1:
                hashes = {}
                for file_path in file_paths:
                    file_hash = self.file_manager.get_file_hash(file_path, hash_algorithm)
                    if file_hash:
                        if file_hash in hashes:
                            if file_hash not in duplicate_hashes:
                                duplicate_hashes[file_hash] = [hashes[file_hash]] # Bắt đầu danh sách trùng lặp
                            duplicate_hashes[file_hash].append(file_path)
                        else:
                            hashes[file_hash] = file_path
        
        print("Hoàn tất tìm kiếm tệp trùng lặp.")
        return duplicate_hashes

    def find_large_files(self, root_dir, min_size_mb=100, limit=50):
        """
        Tìm các tệp lớn nhất trong một thư mục gốc.
        min_size_mb: Kích thước tối thiểu (MB) để được coi là tệp lớn.
        limit: Số lượng tệp lớn nhất muốn trả về.
        """
        large_files = []
        min_size_bytes = min_size_mb * 1024 * 1024

        print(f"Bắt đầu tìm kiếm tệp lớn trong '{root_dir}'...")

        for dirpath, _, filenames in os.walk(root_dir):
            try:
                if not os.access(dirpath, os.R_OK):
                    continue
            except Exception:
                continue

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        if file_size >= min_size_bytes:
                            details = get_file_details(file_path)
                            if details:
                                large_files.append(details)
                except Exception:
                    continue # Bỏ qua các tệp không thể truy cập

        # Sắp xếp theo kích thước giảm dần
        large_files.sort(key=lambda x: x['size'], reverse=True)
        
        print("Hoàn tất tìm kiếm tệp lớn.")
        return large_files[:limit]

    def find_old_unaccessed_files(self, root_dir, days_old=365, limit=50):
        """
        Tìm các tệp cũ và ít được truy cập (hoặc sửa đổi) trong một thư mục gốc.
        days_old: Số ngày tối thiểu để được coi là "cũ".
        limit: Số lượng tệp muốn trả về.
        """
        old_files = []
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)

        print(f"Bắt đầu tìm kiếm tệp cũ trong '{root_dir}'...")

        for dirpath, _, filenames in os.walk(root_dir):
            try:
                if not os.access(dirpath, os.R_OK):
                    continue
            except Exception:
                continue

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    if os.path.isfile(file_path):
                        # Sử dụng thời gian sửa đổi (mtime) vì atime không phải lúc nào cũng đáng tin cậy trên Windows
                        modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                        if modified_time < cutoff_date:
                            details = get_file_details(file_path)
                            if details:
                                old_files.append(details)
                except Exception:
                    continue # Bỏ qua các tệp không thể truy cập

        # Sắp xếp theo thời gian sửa đổi cũ nhất lên đầu
        old_files.sort(key=lambda x: datetime.datetime.strptime(x['modified_time'], '%Y-%m-%d %H:%M:%S'))
        
        print("Hoàn tất tìm kiếm tệp cũ.")
        return old_files[:limit]

