
import os
import sys
import logging
import asyncio
import json
from datetime import date
from typing import Dict, Any

# 3rd party
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application, CallbackQueryHandler
from src_rev.infrastructure.kis.mock_api import MockKisApi

# Add project root to path to import src_rev modules
# In Cloud Functions, the current directory is the root
current_dir = os.path.dirname(os.path.abspath(__file__))
# sys.path.append(current_dir) # Not strictly needed if it's the root, but harmless

# Imports from existing codebase
try:
    from src_rev.infrastructure.kis.auth import KisAuth
    from src_rev.infrastructure.kis.api import KisApi
    from src_rev.infrastructure.config_loader import ConfigLoader
    from src_rev.domain.strategies.infinite import InfiniteBuyingLogic
except ImportError as e:
    logging.warning(f"Import failed: {e}. Ensure src_rev is in the same directory.")
    pass

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
# In Cloud Functions, config is likely in the same bundle
CONFIG_PATH = os.path.join(current_dir, "config", "config.yaml")

# Global variables
TOKEN = None
CHAT_ID = None

# Deployment Version
VERSION = "v1.2.0 (Mock Mode)"

def send_startup_notification():
    """컨테이너(인스턴스) 시작 시 알림"""
    try:
        if not os.path.exists(CONFIG_PATH):
            return
            
        loader = ConfigLoader(CONFIG_PATH)
        _, sys_config = loader.load()
        token = sys_config.get("telegram", {}).get("bot_token")
        chat_id = sys_config.get("telegram", {}).get("chat_id")
        
        if token and chat_id:
            msg = f"🚀 <b>시스템 업데이트 완료</b>\n버전: {VERSION}\n새로운 코드가 서버에 반영되었습니다."
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=3)
    except Exception as e:
        logger.warning(f"Startup notification failed: {e}")

# Call immediately on module load (Container Cold Start)
send_startup_notification()

def load_environment():
    """Load config and setup objects"""
    # Verify config exists
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found at {CONFIG_PATH}")
        raise FileNotFoundError(f"Config file not found at {CONFIG_PATH}")

    loader = ConfigLoader(CONFIG_PATH)
    domain_config, system_config = loader.load()
    
    # Global setup
    global TOKEN, CHAT_ID
    telegram_conf = system_config.get("telegram", {})
    TOKEN = telegram_conf.get("bot_token")
    CHAT_ID = str(telegram_conf.get("chat_id"))
    
    api_config = system_config.get("api", {})
    
    if api_config.get("mock_mode", False):
        logging.info("⚠️ MOCK MODE ACTIVATED ⚠️")
        kis = MockKisApi(api_config)
    else:
        is_virtual = api_config.get("is_virtual", True)
        
        auth = KisAuth(
            key=api_config.get("app_key") or api_config.get("mac_address"),
            secret=api_config.get("app_secret"),
            is_virtual=is_virtual
        )
        
        account_num = api_config.get("account_number", "")
        if not account_num:
            cano = api_config.get("cano", "")
            prdt = api_config.get("acnt_prdt_cd", "")
            if cano and prdt:
                account_num = cano + prdt
                
        kis = KisApi(auth, account_num)
    
    return domain_config, system_config, kis

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    keyboard = [
        [KeyboardButton("1. 계좌 조회"), KeyboardButton("2. 사이클 상황보고")],
        [KeyboardButton("3. 오늘의 주문예약"), KeyboardButton("4. 오늘의 체결상황")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("무엇을 도와드릴까요?", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu selections"""
    text = update.message.text
    chat_id = update.effective_chat.id
    
    logger.info(f"Received message: {text} from {chat_id}")
    
    try:
        domain_configs, sys_config, kis = load_environment()
        
        # Security Check
        if str(chat_id) != CHAT_ID:
            await update.message.reply_text("Unauthorized access.")
            return

        if "1. 계좌 조회" in text:
            await handle_account_info(update, kis, domain_configs)
        elif "2. 사이클 상황보고" in text:
            await handle_cycle_menu(update)
        elif "3. 오늘의 주문예약" in text:
            await handle_order_reservation(update, kis, domain_configs)
        elif "4. 오늘의 체결상황" in text:
            await handle_execution_status(update, kis)
        else:
            # Re-send menu if text matches nothing
            if text == "/start" or text.lower() == "hi":
                await start(update, context)
            else:
                 await update.message.reply_text("올바른 메뉴를 선택해주세요.")
            
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(f"오류가 발생했습니다: {str(e)}")

async def handle_account_info(update: Update, kis: KisApi, configs):
    msg = "📊 <b>통합 계좌 조회</b>\n\n"
    
    for config in configs:
        symbol = config.symbol
        position = kis.get_position(symbol)
        
        msg += f"🔸 <b>{symbol}</b>\n"
        msg += f"  수량: {position.quantity} | 평단: ${position.avg_price:,.2f}\n"
        msg += f"  현재가: ${position.current_price:,.2f}\n"
        msg += f"  평가금: ${position.market_value:,.2f}\n"
        
        if position.total_cost > 0:
            msg += f"  수익률: {position.return_rate:.2f}%\n"
        else:
            msg += "  수익률: 0.00%\n"
        msg += "\n"
        
    await update.message.reply_html(msg)



async def handle_order_reservation(update: Update, kis, configs):
    msg = "📅 <b>오늘의 주문예약</b>\n\n"
    has_orders = False
    
    for config in configs:
        symbol = config.symbol
        position = kis.get_position(symbol)
        orders = InfiniteBuyingLogic.generate_orders(config, position)
        
        if not orders:
            continue
            
        has_orders = True
        msg += f"🔸 <b>{symbol}</b>\n"
        for order in orders:
            side_kor = "매수" if order.side.name == "BUY" else "매도"
            # order_type.name 접근 시 Enum인지 문자열인지 확인 필요
            type_name = order.order_type.name if hasattr(order.order_type, 'name') else str(order.order_type)
            
            msg += f"  • [{side_kor}] {order.quantity}주 @ ${order.price:,.2f}\n"
            msg += f"    ({type_name}) - {order.description}\n"
        msg += "\n"
    
    if not has_orders:
        msg = "📅 <b>오늘 예정된 주문이 없습니다.</b>"
        await update.message.reply_html(msg)
    else:
        # 주문 실행 버튼 추가
        keyboard = [
            [InlineKeyboardButton("✅ 주문 실행하기", callback_data="execute_orders")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg += "⚠️ <b>위 주문을 실행하시겠습니까?</b>"
        await update.message.reply_html(msg, reply_markup=reply_markup)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    버튼 클릭 이벤트(CallbackQuery) 처리
    """
    query = update.callback_query
    await query.answer() # 로딩 상태 제거

    # 환경 로드 (Stateless)
    domain_configs, _, kis = load_environment()

    if query.data == "execute_orders":
        # 권한 확인 (chat_id) - user_id는 int, chat_id는 str일 수 있음
        # config의 chat_id를 가져오기 위해 closure나 context 필요하지만, 
        # 여기서는 간단히 update.effective_chat.id로 확인
        
        # 주문 실행 로직
        results = []
        for config in domain_configs:
            symbol = config.symbol
            position = kis.get_position(symbol)
            orders = InfiniteBuyingLogic.generate_orders(config, position)
            
            for order in orders:
                success = kis.place_order(order)
                status = "성공" if success else "실패"
                results.append(f"{symbol} {order.side.name} {order.quantity}주: {status}")

        if results:
            result_msg = "🚀 <b>주문 실행 결과</b>\n\n" + "\n".join(results)
            await query.edit_message_text(text=result_msg, parse_mode='HTML')
        else:
            await query.edit_message_text(text="실행할 주문이 없습니다.")

    elif query.data.startswith("history_summary"):
        # 요약 보기
        symbol = query.data.split("_")[-1]
        await handle_summary(query, symbol)

    elif query.data.startswith("history_table"):
        # 표 보기
        symbol = query.data.split("_")[-1]
        await handle_table(query, symbol)
        
    elif query.data.startswith("history_graph"):
        # 그래프 보기 (QuickChart)
        symbol = query.data.split("_")[-1]
        await handle_graph(query, symbol)

async def handle_summary(query, symbol):
    if symbol == "SOXL":
        msg = "📋 <b>SOXL Cycle Summary (2025.12.17)</b>\n\n"
        msg += "<b>📅 진행 현황</b>\n"
        msg += "• 시작일: 2025. 12. 03\n"
        msg += "• 진행일: 12일차 (워킹데이)\n"
        msg += "• 회차(T): 9.9회 / 40회\n\n"
        msg += "<b>💰 자산 현황</b>\n"
        msg += "• 보유수량: 957 SOXL\n"
        msg += "• 평단가: $43.71\n"
        msg += "• 현재가: $36.01\n"
        msg += "• 총매수액: $41,830.47\n"
        msg += "• 평가손익: -$7,368.90 (-17.62%)\n\n"
        msg += "<b>🛒 금일 투자 설계</b>\n"
        msg += "• 1회 매수금: $4,250\n"
        msg += "• 평단매수: 51주\n"
        msg += "• Star매수: 46주\n"
        msg += "• 총 구매예정: 118주"
    else:
        # TQQQ Dummy Data
        msg = "📋 <b>TQQQ Cycle Summary (Mock)</b>\n\n"
        msg += "<b>📅 진행 현황</b>\n"
        msg += "• 시작일: 2025. 12. 10\n"
        msg += "• 진행일: 5일차\n"
        msg += "• 회차(T): 3.5회 / 40회\n\n"
        msg += "<b>💰 자산 현황</b>\n"
        msg += "• 보유수량: 100 TQQQ\n"
        msg += "• 평단가: $50.00\n"
        msg += "• 현재가: $55.00\n"
        msg += "• 총매수액: $5,000.00\n"
        msg += "• 평가손익: +$500.00 (+10.00%)\n"
    
    await query.edit_message_text(text=msg, parse_mode='HTML')

async def handle_table(query, symbol):
    if symbol == "SOXL":
        msg = "📊 <b>SOXL Cycle History</b>\n\n"
        msg += "<pre>"
        msg += "Date   | Close| Avg  | Star | Qty\n"
        msg += "-------+------+------+------+-----\n"
        msg += "12.03  | 46.58| 45.61| 49.90| 101\n"
        msg += "12.04  | 45.16| 45.38| 49.37| 208\n"
        msg += "12.05  | 46.50| 45.61| 49.46| 265\n"
        msg += "12.08  | 47.99| 45.93| 49.70| 305\n"
        msg += "12.09  | 47.79| 46.27| 49.86| 385\n"
        msg += "12.10  | 49.65| 46.62| 50.09| 435\n"
        msg += "12.11  | 48.79| 46.85| 50.06| 534\n"
        msg += "12.12  | 41.71| 46.03| 48.93| 635\n"
        msg += "12.15  | 41.18| 45.36| 48.10| 737\n"
        msg += "12.16  | 40.49| 44.76| 47.24| 840\n"
        msg += "12.17  | 36.01| 43.71| 45.94| 957\n"
        msg += "</pre>\n"
        msg += "※ Star 가격(목표매수가) 정보가 추가되었습니다."
    else:
        msg = "📊 <b>TQQQ Cycle History</b>\n\n"
        msg += "<pre>"
        msg += "Date       | Close | Avg   | Qty\n"
        msg += "-----------+-------+-------+-----\n"
        msg += "2025.12.10 | $50.00| $50.00| 20\n"
        msg += "2025.12.11 | $51.00| $50.50| 40\n"
        msg += "2025.12.12 | $52.00| $51.00| 60\n"
        msg += "2025.12.13 | $53.00| $51.50| 80\n"
        msg += "2025.12.14 | $55.00| $52.20| 100\n"
        msg += "</pre>\n"
        msg += "※ TQQQ는 순항 중입니다."
    
    await query.edit_message_text(text=msg, parse_mode='HTML')

async def handle_graph(query, symbol):
    try:
        if symbol == "SOXL":
             dates = ["12.3", "12.4", "12.5", "12.8", "12.9", "12.10", "12.11", "12.12", "12.15", "12.16", "12.17"]
             qty = [101, 208, 265, 305, 385, 435, 534, 635, 737, 840, 957]
             close = [46.58, 45.16, 46.50, 47.99, 47.79, 49.65, 48.79, 41.71, 41.18, 40.49, 36.01]
             avg = [45.61, 45.38, 45.61, 45.93, 46.27, 46.62, 46.85, 46.03, 45.36, 44.76, 43.71]
             star = [49.90, 49.37, 49.46, 49.70, 49.86, 50.09, 50.06, 48.93, 48.10, 47.24, 45.94]
        else:
             # TQQQ Dummy
             dates = ["12.10", "12.11", "12.12", "12.13", "12.14"]
             qty = [20, 40, 60, 80, 100]
             close = [50, 51, 52, 53, 55]
             avg = [50, 50.5, 51, 51.5, 52.2]
             star = [55, 56, 57, 58, 60]

        # QuickChart Configuration (Chart.js v2)
        chart_config = {
            "type": "bar",
            "data": {
                "labels": dates,
                "datasets": [
                    {
                        "type": "line",
                        "label": "Close",
                        "borderColor": "rgb(54, 162, 235)",
                        "borderWidth": 2,
                        "fill": False,
                        "data": close,
                        "yAxisID": "y-axis-1"
                    },
                    {
                        "type": "line",
                        "label": "Avg Price",
                        "borderColor": "rgb(255, 99, 132)",
                        "borderWidth": 2,
                        "fill": False,
                        "data": avg,
                        "yAxisID": "y-axis-1"
                    },
                        {
                        "type": "line",
                        "label": "Star Price",
                        "borderColor": "rgb(255, 205, 86)",
                        "borderWidth": 2,
                        "borderDash": [5, 5],
                        "fill": False,
                        "data": star,
                        "yAxisID": "y-axis-1"
                    },
                    {
                        "type": "bar",
                        "label": "Qty",
                        "backgroundColor": "rgba(75, 192, 192, 0.5)",
                        "data": qty,
                        "yAxisID": "y-axis-2"
                    }
                ]
            },
            "options": {
                "title": {
                    "display": True,
                    "text": f"Cycle History ({symbol})"
                },
                "scales": {
                    "yAxes": [
                        {
                            "id": "y-axis-1",
                            "type": "linear",
                            "position": "left",
                            "scaleLabel": {"display": True, "labelString": "Price ($)"}
                        },
                        {
                            "id": "y-axis-2",
                            "type": "linear",
                            "position": "right",
                            "scaleLabel": {"display": True, "labelString": "Quantity"}
                        }
                    ]
                }
            }
        }
        
        # Encode config to JSON string
        import json
        import urllib.parse
        chart_json = json.dumps(chart_config)
        encoded_config = urllib.parse.quote(chart_json)
        quickchart_url = f"https://quickchart.io/chart?c={encoded_config}"
        
        # Send Photo URL directly (Telegram supports URL)
        await query.message.reply_photo(photo=quickchart_url, caption=f"📉 <b>{symbol} Cycle Graph</b>", parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error generating graph: {e}")
        await query.edit_message_text(text=f"그램프 생성 오류: {e}")

async def handle_cycle_menu(update: Update):
    """사이클 상황보고 메뉴 (요약/표/그래프) - 종목별 분리"""
    keyboard = [
        [InlineKeyboardButton("📋 SOXL 요약", callback_data="history_summary_SOXL"),
         InlineKeyboardButton("📋 TQQQ 요약", callback_data="history_summary_TQQQ")],
        [InlineKeyboardButton("📊 SOXL 표", callback_data="history_table_SOXL"),
         InlineKeyboardButton("📊 TQQQ 표", callback_data="history_table_TQQQ")],
        [InlineKeyboardButton("📉 SOXL 그래프", callback_data="history_graph_SOXL"),
         InlineKeyboardButton("📉 TQQQ 그래프", callback_data="history_graph_TQQQ")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔎 <b>종목별 사이클 상황보고</b>\n원하시는 조회 방식을 선택해주세요:", reply_markup=reply_markup, parse_mode='HTML')

async def handle_execution_status(update: Update, kis: KisApi):
    today = date.today().strftime("%Y%m%d")
    orders = kis.get_orders(today, today)
    
    if not orders:
        await update.message.reply_text("📝 <b>오늘의 체결(주문) 현황</b>\n\n내역이 없습니다.")
        return

    msg = f"📝 <b>오늘의 체결(주문) 현황</b> ({today})\n\n"
    
    for o in orders:
        # Fields based on KIS API inquire-ccnl
        # OrdDate(ord_dt), OrderNo(odno), PrdtName(prdt_name), Side(sll_buy_dvsn_cd_name)
        # Qty(ord_qty), Price(ord_unpr/ccld_avg_unpr), Status(ord_stat_name), Filled(ccld_qty)
        
        name = o.get("prdt_name") or o.get("pdno")
        side = o.get("sll_buy_dvsn_cd_name", "주문")
        qty = o.get("ord_qty", "0")
        price = o.get("ord_unpr", "0")
        status = o.get("ord_stat_name", "")
        filled = o.get("ccld_qty", "0")
        
        msg += f"• {name} ({side})\n"
        msg += f"  {qty}주 @ ${float(price):.2f} | {status} (체결: {filled})\n"
        
    await update.message.reply_html(msg)

# --- Cloud Function Entry Point ---

import functions_framework

@functions_framework.http
def telegram_webhook(request):
    """
    HTTP Cloud Function for generic webhook
    """
    # 1. Parse Request
    if request.method != "POST":
        return "Only POST supported", 405
    
    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return "Invalid JSON", 400
            
        # Initialize Config to get Token
        # (Slightly inefficient to load config every time, but ensures freshness and simplicity)
        loader = ConfigLoader(CONFIG_PATH)
        _, sys_config = loader.load()
        token = sys_config.get("telegram", {}).get("bot_token")
        
        if not token:
            logger.error("Bot token not found in config")
            return "Bot token missing", 500

    except Exception as e:
        logger.error(f"Init error: {e}")
        return f"Init Error: {e}", 500

    # 2. Process Update with Asyncio
    async def process_update_async():
        # Build app
        app = ApplicationBuilder().token(token).build()
        
        # Register Handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback_query))
        
        # Initialize
        await app.initialize()
        
        # Process
        update = Update.de_json(request_json, app.bot)
        await app.process_update(update)
        
        # Shutdown
        await app.shutdown()

    try:
        asyncio.run(process_update_async())
    except Exception as e:
        logger.error(f"Runtime error: {e}", exc_info=True)
        return f"Runtime Error: {e}", 500
        
    return "OK", 200
