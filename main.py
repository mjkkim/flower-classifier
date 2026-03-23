import subprocess
import sys
import os

def run_service(script_name):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(base_dir, script_name)
    
    return subprocess.Popen([sys.executable, script_path])

def main():
    print("프로그램 통합 실행을 시작합니다...")
    
    # 서버 실행
    server_process = run_service("server.py")
    print(f"서버 실행 중... (PID: {server_process.pid})")
    
    # 클라이언트 실행
    client_process = run_service("client.py")
    print(f"클라이언트 실행 중... (PID: {client_process.pid})")
    
    print("\n[안내] 서버와 클라이언트 GUI가 모두 실행되었습니다.")
    print("프로그램을 종료하려면 각 윈도우를 닫거나, 이 터미널에서 Ctrl+C를 누르세요.")
    
    try:
        # 두 프로세스가 모두 종료될 때까지 대기
        server_process.wait()
        client_process.wait()
    except KeyboardInterrupt:
        print("\n프로그램 종료 요청을 받았습니다. 프로세스를 종료합니다...")
        server_process.terminate()
        client_process.terminate()
        print("모든 프로세스가 종료되었습니다.")

if __name__ == "__main__":
    main()
