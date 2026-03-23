import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import datetime
import tensorflow as tf
import numpy as np
import pandas as pd
import socket
import threading
from io import BytesIO
from PIL import Image, ImageFile

# 불완전한 이미지 데이터 처리 허용
ImageFile.LOAD_TRUNCATED_IMAGES = True

# 서버 설정
SERVER_IP = '0.0.0.0'
SERVER_PORT = 8080
SERVER_ADDR = (SERVER_IP, SERVER_PORT)

class FlowerServerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("서버")
        self.root.geometry("800x600")

        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        # 스타일 설정
        style = ttk.Style()
        style.theme_use('aqua') 
        # style.theme_use('clam') # docker 환경에서는 이거 써야 됨
        style.configure("Treeview.Heading", font=("NanumGothic", 10, 'bold'))

        self.create_widgets()

        # 모델 로드
        self.model = None
        self.df = None
        self.infer = None

        self.load_model_and_labels()

        # 서버 및 스레드 관련 변수 초기화
        self.server_socket = None
        self.client_threads = []
        self.client_sockets = []
        self.running = False # 서버 실행 상태

    def create_widgets(self):
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(2, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # 상단 프레임 (상태 + 제어)
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_frame.columnconfigure(0, weight=1)

        # 서버 상태 프레임
        status_frame = ttk.LabelFrame(top_frame, text="서버 상태", padding="10")
        status_frame.grid(row=0, column=0, sticky="ewns")
        
        ttk.Label(status_frame, text="IP 주소:").grid(row=0, column=0, sticky="w")
        self.ip_label = ttk.Label(status_frame, text=str(SERVER_IP), font=("NanumGothic", 10))
        self.ip_label.grid(row=0, column=1, sticky="w")

        ttk.Label(status_frame, text="포트:").grid(row=1, column=0, sticky="w")
        self.port_label = ttk.Label(status_frame, text=str(SERVER_PORT), font=("NanumGothic", 10))
        self.port_label.grid(row=1, column=1, sticky="w")

        ttk.Label(status_frame, text="상태:").grid(row=2, column=0, sticky="w")
        self.status_label = ttk.Label(status_frame, text="Stopped", foreground="red", font=("NanumGothic", 10))
        self.status_label.grid(row=2, column=1, sticky="w")

        # 서버 제어 프레임
        control_frame = ttk.LabelFrame(top_frame, text="서버 제어", padding="10")
        control_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        
        # 버튼들이 프레임 너비에 맞게 확장되도록 설정
        self.start_button = ttk.Button(control_frame, text="서버 시작", command=self.start_server)
        self.start_button.pack(pady=5, fill=tk.X)
        self.stop_button = ttk.Button(control_frame, text="서버 중지", command=self.stop_server, state=tk.DISABLED)
        self.stop_button.pack(pady=5, fill=tk.X)

        # 프로그램 종료 버튼
        ttk.Separator(control_frame, orient='horizontal').pack(fill='x', pady=10)
        self.exit_button = ttk.Button(control_frame, text="프로그램 종료", command=self.close_app)
        self.exit_button.pack(pady=5, fill=tk.X)


        # 클라이언트 목록 프레임
        clients_frame = ttk.LabelFrame(main_frame, text="연결된 클라이언트", padding="10")
        clients_frame.grid(row=1, column=0, sticky="ew", pady=5)
        clients_frame.columnconfigure(0, weight=1)
        clients_frame.rowconfigure(0, weight=1)

        self.client_tree = ttk.Treeview(
            clients_frame, 
            columns=("ip", "port", "time"), 
            show="headings",
            height=5
        )
        self.client_tree.grid(row=0, column=0, sticky="ew")
        
        self.client_tree.heading("ip", text="IP 주소")
        self.client_tree.heading("port", text="포트")
        self.client_tree.heading("time", text="연결 시간")
        
        self.client_tree.column("ip", width=150)
        self.client_tree.column("port", width=100)
        self.client_tree.column("time", width=200)

        # 상세 로그 프레임
        log_frame = ttk.LabelFrame(main_frame, text="상세 로그", padding="10")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(5, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state=tk.DISABLED, font=("NanumGothic", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")

        # 로그 타입별 색상 설정
        self.log_text.tag_config("INFO", foreground="royalblue")
        self.log_text.tag_config("SUCCESS", foreground="green")
        self.log_text.tag_config("ERROR", foreground="red")
        self.log_text.tag_config("WARNING", foreground="orange")

    def load_model_and_labels(self):
        """모델 및 라벨 파일 로드"""
        try:
            self.model = tf.saved_model.load('./model')
            self.df = pd.read_excel('./labels.xlsx')

            # Docker 환경이라면 ./server/디렉토리 기준으로 지정해야 실행된다
            # self.model = tf.saved_model.load('./server/model') 
            # self.df = pd.read_excel('./server/label.xlsx')
            
            # 추론을 위한 함수 시그니처
            self.infer = self.model.signatures['serving_default']
            self.add_log("모델/라벨 로드 완료", "SUCCESS")
        except Exception as e:
            msg = f"모델 또는 라벨 파일 로드 실패: {str(e)}"
            self.add_log(msg, "ERROR")
            self.model = None
            self.df = None
            self.infer = None

    def start_server(self):
        """서버 시작"""
        if self.running:
            self.add_log("서버가 이미 실행 중입니다.", "WARNING")
            return
            
        if self.model is None or self.df is None:
            self.add_log("모델 또는 라벨 파일이 로드되지 않아 서버를 시작할 수 없습니다.", "ERROR")
            return
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(SERVER_ADDR)
            self.server_socket.listen(socket.SOMAXCONN)
            self.server_socket.settimeout(1)

            self.running = True

            self.status_label.config(text="Running", foreground="green")
            self.ip_label.config(text=SERVER_IP)
            self.port_label.config(text=str(SERVER_PORT))
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            # 연결 대기
            threading.Thread(target=self.listen_for_clients, daemon=True).start()
            self.add_log(f"서버가 {SERVER_IP}:{SERVER_PORT}에서 시작되었습니다.", "INFO")

        except Exception as e:
            self.running = False
            self.status_label.config(text="Stopped", foreground="red")
            self.add_log(f'서버 실행 실패: {str(e)}', 'ERROR')
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)

    def stop_server(self):
        """서버 중지"""
        if not self.running:
            self.add_log("이미 중지된 상태입니다.", "WARNING")
            return
        
        self.running = False
        self.add_log("서버 종료중...")

        # 모든 클라이언트 소켓 닫기
        for client_socket in self.client_sockets:
            try:
                client_socket.close()
            except Exception:
                pass
        
        # 모든 클라이언트 스레드 종료 대기
        for thread in self.client_threads:
            if thread.is_alive():
                thread.join(timeout=1)
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

        self.status_label.config(text="Stopped", foreground="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        self.add_log("서버가 중지되었습니다.")
        self.clear_client_tree()

    def listen_for_clients(self) -> None:
        """클라이언트 연결 대기 및 처리 스레드 시작"""
        while self.running:
            try:
                client_socket, client_addr = self.server_socket.accept()

                # 클라이언트 소켓 및 스레드 관리
                self.client_sockets.append(client_socket)
                self.add_log(f"클라이언트 연결: {client_addr}")

                # 클라이언트 목록 업데이트
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.add_client_to_tree(client_addr[0], client_addr[1], now)

                # 클라이언트 처리 스레드 시작
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_addr)
                )
                self.client_threads.append(client_thread)
                client_thread.start()
            
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.add_log(f"클라이언트 연결 대기중 오류: {str(e)}", "ERROR")

    def handle_client(self, client_socket: socket.socket, client_addr: tuple) -> None:
        """단일 클라이언트로부터 데이터를 수신하고 분류하여 결과를 전송"""
        client_ip, client_port = client_addr

        try:
            self.add_log(f"클라이언트 처리 시작: {client_addr}")

            # 8byte로 데이터 크기 수신
            data_size_bytes = client_socket.recv(8)
            if not data_size_bytes:
                self.add_log(f"데이터 크기 수신 실패: {client_addr}", "ERROR")
                return
            
            expected_size = int.from_bytes(data_size_bytes, 'big')
            self.add_log(f"{client_addr} - 예상 데이터 크기: {expected_size} bytes")

            # 청크 사이즈 1024 고정, 실제 데이터 수신
            received_data = b''
            chunk_size = 1024
            while len(received_data) < expected_size:
                chunk = client_socket.recv(chunk_size)
                if not chunk:
                    break
                received_data += chunk
            self.add_log(f"{client_addr} - 수신된 데이터 크기: {len(received_data)} bytes")

            result = "서버 오류가 발생했습니다."
            if len(received_data) != expected_size:
                self.add_log(f"{client_addr} - 수신 데이터 크기가 예상과 다릅니다.", "ERROR")
                result = "데이터 수신 중 오류가 발생했습니다."
            else:
                try:
                    image = Image.open(BytesIO(received_data))
                    self.add_log(f"{client_addr} - 이미지 로드 성공, 분류 중...")

                    prediction = self.classify_image(image)
                    predicted_class_idx = np.argmax(prediction[0])

                    en_label, ko_label = self.get_flower_names_by_index(predicted_class_idx)
                    result = f"이 꽃은 {ko_label}({en_label})인 것 같아요!"
                    self.add_log(f"{client_addr} - 분류 결과: {result}", "SUCCESS")
                
                except Exception as e:
                    self.add_log(f"{client_addr}- 이미지 처리/분류 실패: {str(e)}", "ERROR")
                    result = f"이미지 분류에 실패했습니다: {str(e)}"
            client_socket.sendall(result.encode('utf-8'))

        except Exception as e:
            self.add_log(f"{client_addr} - 처리 중 오류 발생: {str(e)}", "ERROR")
        finally:
            try:
                client_socket.close()
            except Exception:
                pass

            self.remove_client_from_tree(client_ip, client_port)
            if client_socket in self.client_sockets:
                self.client_sockets.remove(client_socket)
            current_thread = threading.current_thread()
            if current_thread in self.client_threads:
                self.client_threads.remove(current_thread)
            
            self.add_log(f"클라이언트 연결 종료됨: {client_addr}")

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """이미지 전처리"""
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        image = image.resize((299, 299))
        arr = np.array(image) / 255.0
        arr = np.expand_dims(arr, axis=0)
        return arr

    def classify_image(self, image: Image.Image) -> np.ndarray:
        """이미지 분류"""
        preprocessed_image = self.preprocess_image(image)
        input_tensor = tf.convert_to_tensor(preprocessed_image, dtype=tf.float32)
        prediction = self.infer(input_tensor)
        output_key = list(self.infer.structured_outputs.keys())[0]
        return prediction[output_key].numpy()
    
    def get_flower_names_by_index(self, index: int):
        """예측된 index에 따른 꽃 이름 반환"""
        return (self.df.iloc[index]['en_class'], self.df.iloc[index]['ko_class'])

    def add_log(self, message, msg_type="INFO"):
        """로그 표시"""
        self.log_text.config(state=tk.NORMAL)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{msg_type.upper()}] {message}\n"
        
        # 로그 삽입
        self.log_text.insert(tk.END, log_entry, msg_type.upper())
        
        # 스크롤을 맨 아래로 이동
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def add_client_to_tree(self, ip, port, time):
        """클라이언트 정보를 Treeview에 추가"""
        self.client_tree.insert("", tk.END, values=(ip, port, time))

    def remove_client_from_tree(self, ip, port):
        """ip, port를 기준으로 클라이언트 정보를 Treeview에서 제거"""
        for item in self.client_tree.get_children():
            values = self.client_tree.item(item, "values")
            if len(values) >= 2 and values[0] == ip and str(values[1]) == str(port):
                self.client_tree.delete(item)
                break

    def clear_client_tree(self):
        """TreeView의 모든 항목 삭제"""
        for item in self.client_tree.get_children():
            self.client_tree.delete(item)

    def close_app(self):
        """프로그램 종료"""

        # 서버가 실행중이면 우선 종료
        if self.running:
            self.stop_server()

        if messagebox.askokcancel("종료 확인", "프로그램을 종료하시겠습니까?"):
            self.root.quit()
            self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = FlowerServerUI(root)
    root.mainloop()