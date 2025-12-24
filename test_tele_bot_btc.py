from keep_alive import keep_alive
import requests
import time
import io
from datetime import datetime
import pandas as pd
import mplfinance as mpf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- CẤU HÌNH ---
TOKEN = "8514126191:AAEDjg_KqmSX4jdEb_4jCxCo1mOLMnTOEso"
CHAT_ID = "7149174491"

CHECK_INTERVAL = 60  # Chu kỳ kiểm tra giá (giây)

# Ngưỡng báo động
BTC_IMG_THRESHOLD = 1000  # Gửi ảnh nếu biến động > 1000 giá
BTC_TXT_THRESHOLD = 500  # Gửi text nếu biến động > 500 giá

ETH_IMG_THRESHOLD = 100  # Gửi ảnh nếu biến động > 100 giá
ETH_TXT_THRESHOLD = 50  # Gửi text nếu biến động > 50 giá


def get_24h_stats(symbol):
    """Lấy thông số biến động 24h"""
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
        res = requests.get(url, timeout=5)
        data = res.json()
        return {
            "priceChangePercent": float(data["priceChangePercent"]),
            "lastPrice": float(data["lastPrice"]),
            "volume": float(data["quoteVolume"]),  # Volume in USDT
        }
    except Exception:
        return {"priceChangePercent": 0.0, "lastPrice": 0.0, "volume": 0.0}


def get_chart_image(symbol, current_price, percent_change, volume_24h):
    """
    Vẽ biểu đồ Nến Nhật (Candlestick) Xịn Xò
    """
    try:
        # Lấy 100 cây nến 1h gần nhất (Tăng số lượng nến)
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=1h&limit=100"
        res = requests.get(url)
        data = res.json()

        # Chuyển dữ liệu sang DataFrame của Pandas
        df = pd.DataFrame(
            data,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "qav",
                "num_trades",
                "taker_base_vol",
                "taker_quote_vol",
                "ignore",
            ],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Ép kiểu dữ liệu sang float
        df = df[["open", "high", "low", "close", "volume"]].astype(float)

        # Cấu hình giao diện (Style Dark Premium)
        # Màu nền đen như cũ
        bg_color = "#121212"
        text_color = "white"

        mc = mpf.make_marketcolors(
            up="#0ECB81",  # Xanh
            down="#F6465D",  # Đỏ
            edge="inherit",
            wick="inherit",
            volume="in",
        )
        s = mpf.make_mpf_style(
            marketcolors=mc,
            base_mpf_style="nightclouds",
            facecolor=bg_color,  # Màu nền chart
            edgecolor=bg_color,  # Màu viền
            gridstyle=":",
            gridcolor="#2A2A2A",  # Màu lưới tối hơn
            y_on_right=True,
            rc={
                "font.size": 10,
                "axes.labelcolor": text_color,
                "xtick.color": "gray",
                "ytick.color": "gray",
                "figure.facecolor": bg_color,
            },
        )

        # Lưu ảnh vào bộ nhớ đệm
        buf = io.BytesIO()

        # Vẽ biểu đồ
        price_color = "#0ECB81" if percent_change >= 0 else "#F6465D"

        fig, axes = mpf.plot(
            df,
            type="candle",
            volume=False,
            style=s,
            ylabel="",
            datetime_format="%H:%M",  # Chỉ hiện giờ phút dưới trục
            xrotation=0,  # Chữ nằm ngang
            hlines=dict(
                hlines=[current_price],
                colors=[price_color],
                linestyle="--",
                linewidths=1,
                alpha=0.7,
            ),
            figsize=(10, 6),
            tight_layout=True,
            returnfig=True,
        )

        # Thêm nhãn giá hiện tại
        ax = axes[0]
        ax.text(
            1.002,
            current_price,
            f"{current_price:,.1f}",
            color="white",
            fontsize=9,
            va="center",
            ha="left",
            fontweight="bold",
            transform=ax.get_yaxis_transform(),
            bbox=dict(facecolor=price_color, edgecolor=price_color, pad=2, alpha=0.8),
        )

        fig.savefig(
            buf, format="png", bbox_inches="tight", pad_inches=0.1, facecolor=bg_color
        )

        buf.seek(0)
        img_data = plt.imread(buf)

        # Tạo Figure mới với header
        fig_final = plt.figure(figsize=(10, 7), facecolor=bg_color)
        ax_final = fig_final.add_axes([0, 0, 1, 1])
        ax_final.axis("off")

        # Vẽ ảnh nến
        # GIẢM chiều cao chart xuống 5.5 để chừa chỗ cho Header thoáng hơn
        ax_final.imshow(img_data, extent=[0, 10, 0, 5.5], aspect="auto")
        ax_final.set_xlim(0, 10)
        ax_final.set_ylim(0, 7)

        # --- HEADER ---
        color_theme = "#0ECB81" if percent_change >= 0 else "#F6465D"

        # 0. Thêm Icon (BTC/ETH)
        try:
            icon_url = ""
            if "BTC" in symbol:
                icon_url = "https://cryptologos.cc/logos/bitcoin-btc-logo.png"
            elif "ETH" in symbol:
                icon_url = "https://cryptologos.cc/logos/ethereum-eth-logo.png"

            if icon_url:
                headers = {"User-Agent": "Mozilla/5.0"}
                response = requests.get(icon_url, headers=headers, timeout=3)
                icon_img = plt.imread(io.BytesIO(response.content), format="png")
                # Vẽ icon vào góc trái trên
                # Đẩy icon lên cao (y=0.83) và thu nhỏ xíu (0.11)
                ax_icon = fig_final.add_axes(
                    [0.05, 0.83, 0.11, 0.11], anchor="NW", zorder=10
                )  # [left, bottom, width, height]
                ax_icon.imshow(icon_img)
                ax_icon.axis("off")
        except Exception as e:
            print(f"Không tải được icon: {e}")

        # 1. Tên Coin & Time (Year added)
        # Đẩy lên cao cho cân đối
        plt.figtext(
            0.17, 0.91, f"{symbol}", fontsize=22, color="white", fontweight="bold"
        )
        plt.figtext(0.38, 0.92, "1H", fontsize=12, color="gray", fontweight="bold")

        # 4. Thời gian (Góc phải trên, có năm)
        now_str = datetime.now().strftime("%H:%M %d/%m/%Y")
        plt.figtext(
            0.95, 0.94, f"Time: {now_str}", fontsize=9, color="gray", ha="right"
        )

        # 2. Giá to
        # Đẩy lên cao
        plt.figtext(
            0.17,
            0.83,
            f"${current_price:,.2f}",
            fontsize=30,
            color=color_theme,
            fontweight="bold",
        )

        # 3. % Thay đổi & Volume
        sign = "+" if percent_change >= 0 else ""
        vol_str = (
            f"{volume_24h/1_000_000_000:.2f}B"
            if volume_24h >= 1_000_000_000
            else f"{volume_24h/1_000_000:.2f}M"
        )

        # 3. % Thay đổi & Volume
        # Đẩy lên cao ngang tầm giá
        plt.figtext(
            0.55,
            0.84,
            f"24h: {sign}{percent_change:.2f}%",
            fontsize=12,
            color=color_theme if percent_change >= 0 else "#F6465D",
        )
        plt.figtext(0.70, 0.84, f"Vol: {vol_str}", fontsize=12, color="gray")

        # Lưu ảnh cuối cùng
        final_buf = io.BytesIO()
        plt.savefig(final_buf, format="png", bbox_inches="tight", facecolor=bg_color)
        final_buf.seek(0)

        plt.close("all")  # Đóng tất cả figure
        return final_buf

    except Exception as e:
        print(f"Lỗi vẽ biểu đồ: {e}")
        return None


def send_telegram(message, chat_id=CHAT_ID, image_buffer=None):
    """Gửi tin nhắn hoặc ảnh"""
    try:
        if image_buffer:
            url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            files = {"photo": image_buffer}
            data = {"chat_id": chat_id, "caption": message}
            requests.post(url, files=files, data=data, timeout=20)
        else:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            params = {"chat_id": chat_id, "text": message}
            requests.get(url, params=params, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Tele: {e}")


def get_futures_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    for i in range(3):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data["price"])
        except Exception:
            time.sleep(1)
    return None


def process_price_check(
    symbol, current_price, last_price, img_threshold, txt_threshold
):
    if current_price is None or last_price is None:
        return last_price

    diff = current_price - last_price
    abs_diff = abs(diff)

    if abs_diff >= txt_threshold:
        icon = "🚀" if diff > 0 else "🩸"
        trend = "TĂNG" if diff > 0 else "GIẢM"
        now_str = datetime.now().strftime("%H:%M %d/%m")

        # Case 1: Biến động mạnh -> Gửi ẢNH
        if abs_diff >= img_threshold:
            stats = get_24h_stats(symbol)
            percent_24h = stats["priceChangePercent"]
            volume_24h = stats["volume"]

            msg = f"{icon} {symbol} {trend} MẠNH (${abs(diff):,.2f})\n🕒 {now_str}"
            print(f"--> Đang vẽ chart {symbol} để gửi (Diff: {diff})...")
            chart_img = get_chart_image(symbol, current_price, percent_24h, volume_24h)
            send_telegram(msg, CHAT_ID, chart_img)

        # Case 2: Biến động vừa -> Gửi TEXT
        else:
            msg = (
                f"{icon} {symbol} {trend} NHẸ\n"
                f"💵 Giá: ${current_price:,.2f}\n"
                f"📉 Thay đổi: {diff:+.2f}\n"
                f"🕒 {now_str}"
            )
            print(f"--> Gửi tin nhắn text {symbol} (Diff: {diff})...")
            send_telegram(msg, CHAT_ID)

        # Cập nhật giá mốc mới sau khi đã báo động
        return current_price

    # Không đủ ngưỡng thì giữ nguyên giá mốc cũ để cộng dồn biến động
    return last_price


def check_incoming_messages(last_update_id):
    """Kiểm tra tin nhắn người dùng gửi đến (Lệnh /start)"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 1}
    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if not data["ok"] or not data["result"]:
            return last_update_id

        for update in data["result"]:
            last_update_id = update["update_id"]

            # Chỉ xử lý tin nhắn văn bản
            if "message" in update and "text" in update["message"]:
                text = update["message"]["text"]
                user_chat_id = update["message"]["chat"]["id"]
                user_name = update["message"]["from"].get("first_name", "Bạn")

                if text == "/start":
                    print(f"📩 Nhận lệnh /start từ {user_name}")
                    # Đã bỏ phần giới thiệu theo yêu cầu
                    pass

        return last_update_id
    except Exception:
        return last_update_id


def main():
    print("🤖 Bot Crypto PRO (Nến Nhật) đang chạy...")

    # Gửi tin khởi động vào nhóm
    last_btc = get_futures_price("BTCUSDT")
    last_eth = get_futures_price("ETHUSDT")
    if last_btc or last_eth:
        send_telegram(
            f"🤖 Bot đã khởi động lại!\nBTC: ${last_btc:,.0f} | ETH: ${last_eth:,.0f}",
            CHAT_ID,
        )

    last_update_id = 0
    last_check_time = time.time()  # Mốc thời gian kiểm tra giá

    while True:
        # 1. Xử lý tin nhắn đến (Chạy liên tục mỗi 1s cho mượt)
        last_update_id = check_incoming_messages(last_update_id)

        # 2. Kiểm tra giá (Chỉ chạy khi đủ thời gian CHECK_INTERVAL)
        current_time = time.time()
        if current_time - last_check_time >= CHECK_INTERVAL:
            last_check_time = current_time  # Cập nhật mốc thời gian

            curr_btc = get_futures_price("BTCUSDT")
            curr_eth = get_futures_price("ETHUSDT")

            # Hiện trạng thái bình thường (Time | BTC | ETH)
            now_str = datetime.now().strftime("%H:%M:%S")
            if curr_btc and curr_eth:
                print(f"{now_str} | BTC: ${curr_btc:,.0f} | ETH: ${curr_eth:,.0f}")

            if curr_btc:
                last_btc = process_price_check(
                    "BTCUSDT", curr_btc, last_btc, BTC_IMG_THRESHOLD, BTC_TXT_THRESHOLD
                )

            if curr_eth:
                last_eth = process_price_check(
                    "ETHUSDT", curr_eth, last_eth, ETH_IMG_THRESHOLD, ETH_TXT_THRESHOLD
                )

        # Nghỉ 1s để không spam server Telegram quá mức
        time.sleep(1)


if __name__ == "__main__":
    keep_alive()  # Chạy web server giả trước để giữ kết nối
    main()  # Sau đó mới chạy bot
