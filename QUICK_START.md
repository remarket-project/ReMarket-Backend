# Hướng Dẫn Chạy Backend ReMarket

## 📋 Yêu Cầu Hệ Thống

- **Python 3.10+**
- **uv** (Python package manager) - [Cài đặt](https://docs.astral.sh/uv/)
- **Docker** (để chạy database) - [Cài đặt](https://www.docker.com/)
- **Git**
- **VS Code** (khuyến nghị)

---

## 🚀 Cách 1: Chạy Backend Trực Tiếp (Khuyến nghị cho phát triển)

### Bước 1: Chuẩn bị môi trường

```bash
# Vào thư mục backend
cd "d:\Đồ Án Tốt Nghiệp\ReMarket-Backend"

# Tạo virtual environment và cài đặt dependencies
uv sync

# Kích hoạt virtual environment
.\.venv\Scripts\Activate.ps1
```

### Bước 2: Khởi động Database (PostgreSQL)

Chạy database trong container Docker:

```bash
# Từ thư mục gốc (d:\Đồ Án Tốt Nghiệp)
docker compose up -d db

# Kiểm tra database chạy thành công
docker compose logs db
```

**Kết quả mong muốn:**

```
db_1  | LOG:  listening on IPv4 address "0.0.0.0", port 5432
db_1  | LOG:  listening on all available addresses
```

### Bước 3: Chạy Backend

```bash
# Từ thư mục ReMarket-Backend
fastapi run app/main.py --reload
```

**Kết quả mong muốn:**

```
INFO:     Uvicorn running on http://127.0.0.1:8000 [Press ENTER to exit]
INFO:     Application startup complete
```

### Bước 4: Truy cập Swagger UI

Mở trình duyệt và đi đến:

```
http://localhost:8000/docs
```

Hoặc API dùng ReDoc:

```
http://localhost:8000/redoc
```

---

## 🐳 Cách 2: Chạy Bằng Docker Compose

### Bước 1: Khởi động toàn bộ stack

```bash
# Từ thư mục gốc (d:\Đồ Án Tốt Nghiệp)
docker compose up -d

# Hoặc nếu muốn xem logs realtime
docker compose up
```

### Bước 2: Kiểm tra các service đang chạy

```bash
docker compose ps
```

**Kết quả mong muốn:**

```
NAME          COMMAND              SERVICE    STATUS      PORTS
db            postgres ...         db         Up 2 mins   5432/tcp
backend       fastapi run ...      backend    Up 2 mins   0.0.0.0:8000->8000/tcp
frontend      npm run preview      frontend   Up 2 mins   0.0.0.0:3000->3000/tcp
```

### Bước 3: Truy cập Swagger

```
http://localhost:8000/docs
```

---

## 📊 Xem Logs Backend

### Phương pháp 1: Xem logs từ Docker

```bash
# Xem logs của backend
docker compose logs backend

# Xem logs realtime (follow)
docker compose logs -f backend

# Xem logs từ 50 dòng cuối cùng
docker compose logs --tail=50 backend

# Xem logs từ service cụ thể và fiter
docker compose logs backend | grep "ERROR"
```

### Phương pháp 2: Xem logs khi chạy trực tiếp

Khi chạy `fastapi run app/main.py --reload`, logs sẽ hiển thị trực tiếp trên terminal:

```bash
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
INFO:     127.0.0.1:8000 "POST /auth/register" 201
INFO:     127.0.0.1:8000 "GET /offers/me/received" 200
```

### Phương pháp 3: Xem logs file (nếu được cấu hình)

```bash
# Nếu logs được lưu vào file
tail -f logs/app.log
```

### Hiểu Logs

| Level       | Ý Nghĩa                  | Ví dụ                                |
| ----------- | ------------------------ | ------------------------------------ |
| **INFO**    | Thông tin bình thường    | `INFO: Application startup complete` |
| **WARNING** | Cảnh báo                 | `WARNING: Deprecated endpoint`       |
| **ERROR**   | Lỗi                      | `ERROR: Database connection failed`  |
| **DEBUG**   | Chi tiết debug (nếu bật) | `DEBUG: Query execution time: 150ms` |

---

## 🔍 Kiểm Tra Endpoints Trên Swagger

### Truy cập Swagger UI

1. **Mở browser**: `http://localhost:8000/docs`
2. **Bạn sẽ thấy:**
   - Danh sách tất cả endpoints
   - Phân loại theo tags (Auth, Listings, Orders, Reviews, v.v.)
   - Schema của request/response

### Kiểm Tra Endpoint (Ví dụ)

#### 1️⃣ **Đăng Ký (Register)**

1. Scroll đến section **auth** → **POST /auth/register**
2. Click vào endpoint
3. Click nút **"Try it out"**
4. Điền dữ liệu:
   ```json
   {
     "email": "testuser@example.com",
     "password": "SecurePass123!",
     "full_name": "Test User",
     "phone": "0123456789"
   }
   ```
5. Click **"Execute"**
6. **Tiếp nhận Response:**
   ```json
   {
     "access_token": "eyJhbGc...",
     "refresh_token": "xyz...",
     "token_type": "bearer",
     "user": {
       "id": "550e8400-e29b-41d4-a716-446655440000",
       "email": "testuser@example.com",
       "full_name": "Test User"
     }
   }
   ```

#### 2️⃣ **Đăng Nhập (Login)**

1. Scroll đến section **auth** → **POST /auth/login**
2. Click **"Try it out"**
3. Điền dữ liệu:
   ```json
   {
     "username": "testuser@example.com",
     "password": "SecurePass123!"
   }
   ```
4. Click **"Execute"**

#### 3️⃣ **Sử dụng Access Token**

Sau khi đăng nhập/đăng ký, bạn sẽ có `access_token`.

**Các endpoint yêu cầu authentication:**

1. Click nút **"Authorize"** ở góc phải trên
2. Paste token vào:
   ```
   Bearer eyJhbGc...
   ```
3. Click **"Authorize"** → **"Close"**

Bây giờ tất cả requests sẽ tự động gửi token.

#### 4️⃣ **Tạo Bài Đăng (Create Listing)**

1. Scroll đến section **Listings** → **POST /listings/**
2. Click **"Try it out"**
3. Điền dữ liệu:
   ```json
   {
     "title": "iPhone 13 Pro",
     "description": "Điện thoại Apple chất lượng cao",
     "category_id": "550e8400-e29b-41d4-a716-446655440001",
     "price": 15000000,
     "condition_grade": "like_new",
     "location": "Hà Nội"
   }
   ```
4. Click **"Execute"**

#### 5️⃣ **Kiểm Tra Các Endpoint Mới (FIX #5-8)**

**FIX #5 - Cập nhật trạng thái đơn hàng:**

- Endpoint: `PATCH /orders/{order_id}/status`
- Request:
  ```json
  {
    "status": "CONFIRMED"
  }
  ```

**FIX #6 - Xem ratings của user:**

- Endpoint: `GET /users/{user_id}`
- Sẽ hiển thị: `rating_avg`, `rating_count`, `trust_score`

**FIX #7 - Rate limiting:**

- Chạy endpoint 11 lần trong 1 giờ sẽ nhận lỗi:
  ```json
  {
    "detail": "Rate limit exceeded: 10 requests per 1 hour"
  }
  ```

**FIX #8 - Password validation:**

- Thử đăng ký với mật khẩu yếu → Nhận lỗi:
  ```json
  {
    "detail": "Mật khẩu phải chứa ít nhất một ký tự in hoa"
  }
  ```

---

## 🧪 Chạy Tests

### Chạy tất cả tests

```bash
bash ./scripts/test.sh
```

### Chạy test của file cụ thể

```bash
pytest tests/api/test_auth.py -v
```

### Chạy test với coverage

```bash
pytest --cov=app tests/
```

---

## 🛠️ Troubleshooting

### ❌ Lỗi: `ModuleNotFoundError: No module named 'app'`

**Giải pháp:**

```bash
# Kích hoạt lại virtual environment
cd "d:\Đồ Án Tốt Nghiệp\ReMarket-Backend"
.\.venv\Scripts\Activate.ps1

# Hoặc cài lại dependencies
uv sync
```

### ❌ Lỗi: `Connection refused` (Database)

**Giải pháp:**

```bash
# Kiểm tra database chạy chưa
docker compose ps db

# Nếu chưa, khởi động database
docker compose up -d db

# Kiểm tra logs
docker compose logs db
```

### ❌ Lỗi: Port 8000 đang được sử dụng

**Giải pháp:**

```bash
# Dừng process đang sử dụng port 8000
netstat -ano | findstr :8000

# Hoặc chạy backend trên port khác
fastapi run app/main.py --port 8001 --reload
```

### ❌ Lỗi: `SQLALCHEMY_DATABASE_URL` không được xác định

**Giải pháp:**

- Kiểm tra file `.env` trong thư mục `ReMarket-Backend`
- Hoặc xem file `app/core/config.py` để biết các biến environment cần thiết

---

## 📝 Ghi Chú Quan Trọng

### Development Mode (`--reload`)

```bash
fastapi run app/main.py --reload
```

✅ **Ưu điểm:**

- Tự động reload khi code thay đổi
- Dễ debug

❌ **Nhược điểm:**

- Nếu có lỗi cú pháp, server sẽ crash
- Chậm hơn production mode

### Production Mode

```bash
fastapi run app/main.py
```

✅ **Ưu điểm:**

- Nhanh hơn
- Ổn định hơn

❌ **Nhược điểm:**

- Phải restart lại server để applied code changes

---

## 🔗 Quick Links

| Tài nguyên         | URL                                       |
| ------------------ | ----------------------------------------- |
| **Swagger UI**     | http://localhost:8000/docs                |
| **ReDoc API**      | http://localhost:8000/redoc               |
| **OpenAPI JSON**   | http://localhost:8000/openapi.json        |
| **Frontend**       | http://localhost:3000                     |
| **Database Admin** | localhost:5432 (via pgAdmin hoặc DBeaver) |

---

## ✅ Checklist Khởi Động

- [ ] Cài đặt Python 3.10+
- [ ] Cài đặt `uv`
- [ ] Chạy `uv sync` trong thư mục backend
- [ ] Khởi động database: `docker compose up -d db`
- [ ] Chạy backend: `fastapi run app/main.py --reload`
- [ ] Mở Swagger: http://localhost:8000/docs
- [ ] Test endpoint (ví dụ: POST /auth/register)
- [ ] Xem logs khi gọi API

---

**Happy Coding! 🎉**
