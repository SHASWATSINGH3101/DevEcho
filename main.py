import os
import subprocess
import time

def run_script(script_name: str) -> None:
    """Run a Python script using subprocess."""
    print(f"Running {script_name}...")
    subprocess.run(["python", script_name], check=True)

def wait_for_data(directory: str, extension: str, timeout: int = 10) -> None:
    """Wait until at least one file with the given extension is found in the directory."""
    print("Waiting for data to be available...")
    start_time = time.time()
    while True:
        if any(filename.endswith(extension) for filename in os.listdir(directory)):
            print("Data collection completed. Proceeding to RAG...")
            return
        if time.time() - start_time > timeout:
            raise FileNotFoundError(f"Data not found in '{directory}'. Data collection may have failed.")
        time.sleep(1)

def main():
    data_dir = './data'
    # Ensure the data directory exists
    os.makedirs(data_dir, exist_ok=True)

    # Step 1: Run data collection (knowledge_base.py)
    print("Collecting data using knowledge_base.py...")
    run_script("knowledge_base.py")
    
    # Wait until a .txt file is available in the data directory
    wait_for_data(data_dir, ".txt", timeout=10)

    # Step 2: Run RAG process (knowledge_retrieve.py)Summarize
    print("Running RAG process using knowledge_retrieve.py...")
    run_script("knowledge_retrieve.py")

    print('Making posts using post_gen.py...')
    run_script('post_gen.py')
    print("Process completed!")

if __name__ == "__main__":
    main()
