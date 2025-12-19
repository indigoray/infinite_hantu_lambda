import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from src_rev.domain.strategies.infinite import InfiniteBuyingLogic

logger = logging.getLogger(__name__)

def generate_reservation_message(configs, kis):
    """
    오늘의 주문 예약을 확인하고 메시지를 생성합니다.
    Returns:
        tuple: (message_text, has_orders)
    """
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
        
    return msg, has_orders

def execute_daily_orders(configs, kis):
    """
    예약된 주문을 실제로 실행합니다.
    """
    results = []
    for config in configs:
        symbol = config.symbol
        position = kis.get_position(symbol)
        orders = InfiniteBuyingLogic.generate_orders(config, position)
        
        for order in orders:
            success = kis.place_order(order)
            status = "성공" if success else "실패"
            results.append(f"{symbol} {order.side.name} {order.quantity}주: {status}")

    if results:
        result_msg = "🚀 <b>주문 실행 결과</b>\n\n" + "\n".join(results)
    else:
        result_msg = "실행할 주문이 없습니다."
        
    return result_msg
