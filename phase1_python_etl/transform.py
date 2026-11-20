"""
T - TRANSFORM: làm sạch và chuẩn hoá dữ liệu TRƯỚC khi đưa vào warehouse.
(Đây là chữ T đứng GIỮA trong E-T-L: biến đổi bằng Python, ngoài warehouse.)

Mỗi hàm nhận DataFrame thô và trả về (DataFrame sạch, {lý do loại bỏ: số dòng}).
Mọi quy tắc làm sạch nằm Ở MỘT CHỖ này -> mọi analyst dùng chung một phiên bản sự thật.

Lưu ý: phase này chỉ LÀM SẠCH (sửa lỗi, chuẩn hoá). Chưa MÔ HÌNH HOÁ (fact/dimension), để phase 2.
"""
import re
import unicodedata

import pandas as pd

Dropped = dict[str, int]


# ---------------------------------------------------------------- helpers
def normalize_city(name: str | None) -> str | None:
    """
    'São Paulo ' -> 'sao paulo'   |   'sa£o paulo' -> 'sao paulo'
    Bỏ dấu, viết thường, chỉ giữ chữ/số/khoảng trắng/'/-, gộp khoảng trắng.
    Giới hạn: 'sãopaulo' (dính chữ) vẫn thành 'saopaulo'. Sửa triệt để cần bảng tra tên chuẩn.
    """
    if name is None or pd.isna(name):
        return None
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9 '\-]", "", s)
    return re.sub(r"\s+", " ", s).strip() or None


def to_float(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Postgres NUMERIC -> Python Decimal -> đổi sang float để tính toán nhanh."""
    for c in cols:
        df[c] = df[c].astype(float)
    return df


# 2 category không có trong bảng dịch gốc -> mình bổ sung (quy tắc nghiệp vụ, ghi rõ ràng)
MISSING_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_processors",
}


# ---------------------------------------------------------------- bảng FULL LOAD
def transform_product_category_name_translation(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    extra = pd.DataFrame(MISSING_TRANSLATIONS.items(), columns=df.columns)
    return pd.concat([df, extra], ignore_index=True), {}


def transform_customers(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = df.copy()
    df["customer_city"] = df["customer_city"].map(normalize_city)
    df["customer_zip_code_prefix"] = df["customer_zip_code_prefix"].str.zfill(5)
    df["customer_state"] = df["customer_state"].str.upper().str.strip()
    return df, {}


def transform_sellers(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = df.copy()
    df["seller_city"] = df["seller_city"].map(normalize_city)
    df["seller_zip_code_prefix"] = df["seller_zip_code_prefix"].str.zfill(5)
    df["seller_state"] = df["seller_state"].str.upper().str.strip()
    return df, {}


def transform_products(df: pd.DataFrame, translation: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = df.rename(columns={                      # sửa lỗi chính tả của nguồn
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    df["product_category_name"] = df["product_category_name"].fillna("unknown")
    # Thêm cột tên tiếng Anh ngay tại đây -> analyst không phải tự JOIN bảng dịch nữa
    df = df.merge(translation, on="product_category_name", how="left")
    df["product_category_name_english"] = df["product_category_name_english"].fillna("unknown")
    return df, {}


def transform_geolocation(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    """
    Nguồn: ~1 triệu dòng, NHIỀU toạ độ cho cùng 1 zip, tên thành phố viết lung tung.
    Đích: MỖI zip MỘT dòng (lat/lng trung vị + tên thành phố phổ biến nhất sau chuẩn hoá).
    """
    df = df.copy()
    df["geolocation_city"] = df["geolocation_city"].map(normalize_city)
    df["geolocation_zip_code_prefix"] = df["geolocation_zip_code_prefix"].str.zfill(5)
    out = (df.groupby("geolocation_zip_code_prefix")
             .agg(lat=("geolocation_lat", "median"),
                  lng=("geolocation_lng", "median"),
                  city=("geolocation_city", lambda s: s.mode().iat[0]),
                  state=("geolocation_state", lambda s: s.mode().iat[0]))
             .reset_index()
             .rename(columns={"geolocation_zip_code_prefix": "zip_code_prefix"}))
    return out, {"gộp toạ độ trùng zip": len(df) - len(out)}


# ---------------------------------------------------------------- bảng INCREMENTAL
def transform_orders(df: pd.DataFrame, items: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = df.copy()
    df["order_status"] = df["order_status"].str.lower().str.strip()
    # Cờ chất lượng: KHÔNG xoá đơn, mà đánh dấu để người dùng tự quyết
    df["has_items"] = df["order_id"].isin(items["order_id"])
    df["is_delivered_missing_date"] = (df["order_status"] == "delivered") & df["order_delivered_customer_date"].isna()
    return df, {}


def transform_order_items(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = to_float(df.copy(), ["price", "freight_value"])
    bad = df["price"] <= 0
    return df[~bad], {"price <= 0": int(bad.sum())}


def transform_order_payments(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    df = to_float(df.copy(), ["payment_value"])
    bad = df["payment_type"] == "not_defined"
    return df[~bad], {"payment_type = not_defined": int(bad.sum())}


def transform_order_reviews(df: pd.DataFrame) -> tuple[pd.DataFrame, Dropped]:
    """
    Nguồn: review_id KHÔNG unique, và 1 đơn có thể có nhiều review.
    Quy tắc nghiệp vụ (mình chọn và ghi rõ): mỗi đơn chỉ giữ review MỚI NHẤT.
    -> Sau transform: order_id là khoá duy nhất của bảng này.
    """
    df = df.sort_values("review_answer_timestamp")
    out = df.drop_duplicates(subset="order_id", keep="last")
    for c in ["review_comment_title", "review_comment_message"]:
        out[c] = out[c].str.replace(r"\s+", " ", regex=True).str.strip()  # bỏ xuống dòng trong comment
    return out, {"review cũ của cùng 1 đơn": len(df) - len(out)}
