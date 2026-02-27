print("=== BOT CHỐT ĐƠN THUỐC LÀO ===")
ten = input("Tên/anh/chị là gì: ")
so_luong = int(input("Anh/chị muốn mua mấy gói: "))
gia = 80000
tong_tien = so_luong * gia

# nếu mua từ 5 gói trở lên giảm 10%
if so_luong >=5:
   giam = tong_tien * 0.1
   tong_tien = tong_tien - giam
   print("Anh/chị được giảm 10%:", int(giam), "đồng")

print("-----")
print("cảm ơn", ten)
print("Anh/chị mua", so_luong, "gói")
print("Tổng tiền:", int(tong_tien), "đồng")
print("Bên em sẽ liên hệ xác nhận và gửi hàng ạ!")