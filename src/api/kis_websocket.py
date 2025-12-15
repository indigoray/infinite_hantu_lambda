import asyncio
import json
import logging
import websockets
import time
from datetime import datetime
from typing import Callable, Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

logger = logging.getLogger(__name__)

class KISWebSocketClient:
    """한국투자증권 WebSocket 클라이언트 - 실시간 체결통보"""
    
    def __init__(self, app_key: str, app_secret: str, hts_id: str, is_virtual: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.hts_id = hts_id
        self.is_virtual = is_virtual
        
        # WebSocket URL
        if is_virtual:
            self.ws_url = "ws://ops.koreainvestment.com:31000"  # 모의투자
        else:
            self.ws_url = "ws://ops.koreainvestment.com:21000"  # 실전투자
            
        self.approval_key = None
        self.websocket = None
        self.running = False
        
        # 체결통보 콜백 함수
        self.execution_callback: Optional[Callable] = None
        
        # AES 복호화 키 (WebSocket 접속시 발급됨)
        self.aes_key = ""
        self.aes_iv = ""
        
    async def connect(self):
        """WebSocket 연결"""
        try:
            # 1. 접속키 발급
            self.approval_key = await self._get_approval_key()
            if not self.approval_key:
                logger.error("WebSocket 접속키 발급 실패")
                return False
                
            logger.info(f"WebSocket 접속키 발급 완료: {self.approval_key[:10]}...")
            
            # 2. WebSocket 연결
            self.websocket = await websockets.connect(
                self.ws_url, 
                ping_interval=None,
                close_timeout=10
            )
            
            logger.info("WebSocket 연결 성공")
            self.running = True
            
            # 3. 체결통보 구독
            await self._subscribe_execution_notice()
            
            # 4. 메시지 수신 루프 시작
            await self._message_loop()
            
        except Exception as e:
            logger.error(f"WebSocket 연결 실패: {str(e)}")
            await self.disconnect()
            return False
            
    async def disconnect(self):
        """WebSocket 연결 종료"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        logger.info("WebSocket 연결 종료")
        
    async def _get_approval_key(self) -> str:
        """WebSocket 접속키 발급"""
        import aiohttp
        
        if self.is_virtual:
            url = "https://openapivts.koreainvestment.com:29443/oauth2/Approval"
        else:
            url = "https://openapi.koreainvestment.com:9443/oauth2/Approval"
            
        headers = {"content-type": "application/json"}
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "secretkey": self.app_secret
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await asyncio.sleep(0.05)  # Rate limit
                async with session.post(url, headers=headers, json=data) as response:
                    result = await response.json()
                    return result.get("approval_key", "")
                    
        except Exception as e:
            logger.error(f"접속키 발급 실패: {str(e)}")
            return ""
            
    async def _subscribe_execution_notice(self):
        """해외주식 체결통보 구독"""
        try:
            # H0GSCNI0: 해외주식 체결통보
            subscribe_data = {
                "header": {
                    "approval_key": self.approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0GSCNI0",
                        "tr_key": self.hts_id
                    }
                }
            }
            
            await self.websocket.send(json.dumps(subscribe_data))
            logger.info("해외주식 체결통보 구독 신청 완료")
            
        except Exception as e:
            logger.error(f"체결통보 구독 실패: {str(e)}")
            
    async def _message_loop(self):
        """메시지 수신 루프"""
        try:
            while self.running and self.websocket:
                try:
                    # 메시지 수신 (타임아웃 5초)
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=5.0
                    )
                    
                    await self._process_message(message)
                    
                except asyncio.TimeoutError:
                    # 타임아웃은 정상 (ping-pong 용)
                    continue
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket 연결이 종료됨")
                    break
                    
        except Exception as e:
            logger.error(f"메시지 루프 오류: {str(e)}")
        finally:
            await self.disconnect()
            
    async def _process_message(self, message: str):
        """수신 메시지 처리"""
        try:
            if message.startswith('0'):
                # 일반 응답 메시지
                parts = message.split('|')
                if len(parts) >= 4:
                    tr_id = parts[1]
                    
                    if tr_id == "H0GSCNI0":
                        # 체결통보 메시지인 경우
                        if len(parts) >= 4:
                            # AES 복호화 키 추출
                            if len(parts) >= 6:
                                self.aes_key = parts[4]
                                self.aes_iv = parts[5]
                                
            elif message.startswith('1'):
                # 실시간 데이터
                parts = message.split('|')
                if len(parts) >= 4:
                    tr_id = parts[1]
                    
                    if tr_id in ["H0GSCNI0", "H0GSCNI9"]:
                        # 해외주식 체결통보 처리
                        await self._process_execution_notice(parts[3])
                        
            else:
                # JSON 메시지 (에러, PINGPONG 등)
                try:
                    json_data = json.loads(message)
                    tr_id = json_data.get("header", {}).get("tr_id")
                    
                    if tr_id == "PINGPONG":
                        # 핑퐁은 무시
                        pass
                    else:
                        # 에러 메시지 처리
                        rt_cd = json_data.get("body", {}).get("rt_cd")
                        if rt_cd == "1":
                            msg1 = json_data.get("body", {}).get("msg1", "")
                            if msg1 != "ALREADY IN SUBSCRIBE":
                                logger.error(f"WebSocket 에러: {msg1}")
                                
                except json.JSONDecodeError:
                    logger.debug(f"JSON 파싱 실패: {message[:100]}...")
                    
        except Exception as e:
            logger.error(f"메시지 처리 오류: {str(e)}")
            
    async def _process_execution_notice(self, encrypted_data: str):
        """체결통보 데이터 처리"""
        try:
            if not self.aes_key or not self.aes_iv:
                logger.warning("AES 키가 없어 체결통보 복호화 불가")
                return
                
            # AES 복호화
            decrypted_data = self._aes_decrypt(encrypted_data, self.aes_key, self.aes_iv)
            
            if not decrypted_data:
                return
                
            # 데이터 파싱
            fields = decrypted_data.split('^')
            
            if len(fields) < 13:
                logger.warning("체결통보 데이터 필드 부족")
                return
                
            # 체결통보인지 확인 (12번째 필드가 '2'이면 체결통보)
            if fields[12] == '2':
                execution_data = {
                    "customer_id": fields[0],
                    "account_no": fields[1],
                    "order_no": fields[2],
                    "original_order_no": fields[3],
                    "side": "매수" if fields[4] == "02" else "매도",  # 매도매수구분
                    "modify_type": fields[5],  # 정정구분
                    "order_type": fields[6],  # 주문종류2
                    "symbol": fields[7],  # 단축종목코드
                    "executed_qty": int(fields[8]) if fields[8] else 0,  # 체결수량
                    "executed_price": float(fields[9]) if fields[9] else 0.0,  # 체결단가
                    "executed_time": fields[10],  # 체결시간
                    "reject_yn": fields[11],  # 거부여부
                    "execution_yn": fields[12],  # 체결여부
                    "accept_yn": fields[13] if len(fields) > 13 else "",  # 접수여부
                    "branch_no": fields[14] if len(fields) > 14 else "",  # 지점번호
                    "order_qty": int(fields[15]) if len(fields) > 15 else 0,  # 주문수량
                    "account_name": fields[16] if len(fields) > 16 else "",  # 계좌명
                    "stock_name": fields[17] if len(fields) > 17 else ""  # 체결종목명
                }
                
                logger.info(f"📨 실시간 체결통보 수신: {execution_data['symbol']} {execution_data['side']} {execution_data['executed_qty']}주")
                
                # 콜백 함수 호출
                if self.execution_callback:
                    await self._call_callback(execution_data)
                    
        except Exception as e:
            logger.error(f"체결통보 처리 오류: {str(e)}")
            
    def _aes_decrypt(self, encrypted_data: str, key: str, iv: str) -> str:
        """AES256 복호화"""
        try:
            cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
            decrypted = cipher.decrypt(b64decode(encrypted_data))
            return unpad(decrypted, AES.block_size).decode('utf-8')
        except Exception as e:
            logger.error(f"AES 복호화 실패: {str(e)}")
            return ""
            
    async def _call_callback(self, execution_data: dict):
        """콜백 함수 호출"""
        try:
            if self.execution_callback:
                if asyncio.iscoroutinefunction(self.execution_callback):
                    await self.execution_callback(execution_data)
                else:
                    self.execution_callback(execution_data)
        except Exception as e:
            logger.error(f"콜백 호출 오류: {str(e)}")
            
    def set_execution_callback(self, callback: Callable):
        """체결통보 콜백 함수 설정"""
        self.execution_callback = callback
        logger.info("체결통보 콜백 함수 등록 완료")
        
    async def start_async(self):
        """비동기로 WebSocket 클라이언트 시작"""
        while True:
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"WebSocket 연결 오류: {str(e)}")
                
            if not self.running:
                break
                
            # 재연결 대기
            logger.info("5초 후 WebSocket 재연결 시도...")
            await asyncio.sleep(5) 