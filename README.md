# ApacheCon 2022 IoT Demo

This repository contains the code for an IoT demo showcasing integration with Apache IoTDB and Zenoh for data ingestion and visualization/control via a Python Panel application.

This `feature/zenoh-api-upgrade` branch specifically focuses on upgrading the Zenoh API to the latest stable version.

## Architecture

The demo consists of three main components running as separate processes on your local machine:

1.  **Zenoh Router (`zenohd`):** The core communication middleware enabling efficient data distribution.
2.  **Apache IoTDB:** A high-performance time-series database optimized for IoT data.
3.  **Panel Service (Python):** Your application that interacts with Zenoh to send/receive data, and with IoTDB to store and retrieve time-series data.

All services communicate over `localhost`.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

* **Git:** For cloning the repository.
    * **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install git`
    * **macOS:** `brew install git` (if Homebrew is installed) or install from [git-scm.com](https://git-scm.com/downloads)
    * **Windows:** Install from [git-scm.com](https://git-scm.com/downloads)
* **Python 3.9+ and pip:** For running the Panel service.
    * **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install python3 python3-pip`
    * **macOS:** `brew install python`
    * **Windows:** Download installer from [python.org](https://www.python.org/downloads/)
* **Java 8 or higher (JDK):** Required for Apache IoTDB.
    * **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install openjdk-11-jdk` (or `openjdk-17-jdk`)
    * **macOS:** `brew install openjdk@11` (or `openjdk@17`) and follow instructions to set `JAVA_HOME`.
    * **Windows:** Download installer from [oracle.com/java/technologies/downloads/](https://www.oracle.com/java/technologies/downloads/)
* **`curl` (optional, for Zenoh healthcheck):**
    * Usually pre-installed on Linux/macOS.
    * **Windows:** Available via Git Bash or can be installed separately.

## Deployment and Running Instructions (Command Line)

Follow these steps in **separate terminal windows** for each service, or use background processes if you prefer.

**1. Clone the Repository:**

Open your terminal or command prompt and clone the repository:

```bash
git clone https://github.com/ottlukas/ApacheCon_2022_IoT.git
cd ApacheCon_2022_IoT
git checkout feature/zenoh-api-upgrade # Ensure you are on the correct branch
```

**2. Start Zenoh Router (`zenohd`):**

Navigate to the repository's root directory. If you haven't already, make `zenohd-linux-x86_64` executable:

```bash
chmod +x zenohd-linux-x86_64
```

Then, run the Zenoh router:

```bash
./zenohd-linux-x86_64
```

You should see log output indicating the router has started, typically listening on `0.0.0.0:7447`.

**(Optional) Zenoh Health Check:**
In a new terminal, you can check if Zenoh is running using `curl` (if installed):
```bash
curl http://localhost:8000/router/status
# Expected output: {"status":"Router status: id=... uptime_ms=... sessions=... storages=... subscriptions=...}" (details may vary)
```

**3. Start Apache IoTDB:**

Navigate to the `iotdb` subdirectory:

```bash
cd iotdb
```

Download Apache IoTDB (if you haven't already). The script will place it in a versioned subdirectory (e.g., `apache-iotdb-1.3.1-server-bin`):
```bash
./download_iotdb.sh # You might need to chmod +x download_iotdb.sh first
```

Go into the IoTDB server directory (adjust version if needed):
```bash
cd apache-iotdb-*-server-bin # Or the specific version you downloaded
```

Start the IoTDB server:
```bash
./sbin/start-server.sh -c # Starts ConfigNode
./sbin/start-server.sh -d # Starts DataNode
```
Wait a few moments for IoTDB to initialize. You can check its logs in the `iotdb/logs` directory (relative to the repo root). Look for messages indicating successful startup.

**4. Set up Python Environment and Install Dependencies:**

Navigate back to the repository's root directory:
```bash
cd ../.. # From iotdb/apache-iotdb-X.X.X-server-bin
# Or simply 'cd /path/to/ApacheCon_2022_IoT' if you know the full path
```

It's recommended to use a Python virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# .venv\Scriptsctivate   # On Windows
```

Install the required Python packages:
```bash
pip install -r panel/requirements.txt
```

**5. Run the Panel Application (MQTT & IoTDB Demo):**

Ensure your Zenoh router and IoTDB are running.

In the terminal where your virtual environment is active, run the Panel application:
```bash
python panel/panel_app.py
```
You should see log output from the Panel application indicating it's connecting to Zenoh and attempting to connect to IoTDB. The Panel UI should be accessible in your web browser (typically at `http://localhost:5006/panel_app`).

## End-to-End Testing and Verification

1.  **Open Panel UI:** Open `http://localhost:5006/panel_app` in your web browser.
2.  **Observe Data Flow (Simulated Sensor):**
    *   The `zenoh_producer.py` script (run as part of `panel_app.py` in this version if "Start External Producer" is checked or by default) simulates a sensor sending data (e.g., temperature) via Zenoh.
    *   You should see this data appearing in the "Zenoh Subscriber Data" section of the Panel UI.
    *   The Panel application also subscribes to this Zenoh topic and should display the received messages.
3.  **Check IoTDB Storage:**
    *   The Panel application is configured to store the received sensor data into Apache IoTDB.
    *   In the Panel UI, use the "Fetch from IoTDB" button or similar control to query data from a specific time range.
    *   Verify that the data shown matches what was observed from the Zenoh stream.
4.  **Test Control Command (if applicable):**
    *   If the demo includes a control aspect (e.g., sending a command back to a device via Zenoh from the Panel UI), test this functionality. Observe logs on both the Panel service and any simulated device/subscriber to confirm the command is sent and received. (This specific branch focuses on Zenoh API upgrade, so advanced control features might vary).

## Key Log Indicators

*   **`zenohd`:** Look for lines like `[INFO ] zenoh_router::service: Listener=[<ListenerConfig V4(0.0.0.0:7447, Tcp)>]`
*   **Apache IoTDB:**
    *   ConfigNode: `logs/log_confignode_all.log` - look for successful startup messages.
    *   DataNode: `logs/log_datanode_all.log` - look for successful startup and registration with ConfigNode.
*   **`panel_app.py`:**
    *   `INFO:root:Successfully connected to Zenoh router`
    *   `INFO:root:Session opened with IoTDB`
    *   Log messages indicating data received from Zenoh and data being written/read from IoTDB.

## Cleaning Up

To stop the services:

1.  **Panel Application:** Press `Ctrl+C` in the terminal where `panel_app.py` is running. Deactivate the virtual environment if you used one (`deactivate`).
2.  **Apache IoTDB:**
    ```bash
    cd /path/to/ApacheCon_2022_IoT/iotdb/apache-iotdb-X.X.X-server-bin # Adjust path
    ./sbin/stop-server.sh # Stops DataNode and ConfigNode
    ```
3.  **Zenoh Router:** Press `Ctrl+C` in the terminal where `zenohd-linux-x86_64` is running.

## Troubleshooting Tips

*   **Port Conflicts:** If a service fails to start, check if another application is using the required port (e.g., 7447 for Zenoh, 8000 for Zenoh REST API, 6667/9093 for IoTDB, 5006 for Panel).
*   **Firewall:** Ensure your firewall is not blocking communication between the services on `localhost`.
*   **Java Version/`JAVA_HOME`:** Double-check your Java installation and `JAVA_HOME` environment variable if IoTDB fails to start.
*   **Python Dependencies:** Ensure all packages in `panel/requirements.txt` are installed correctly in your active Python environment.
*   **Zenoh Version Compatibility:** This branch uses a specific Zenoh API. Ensure client libraries match the `zenohd` version if you are modifying components. The provided `zenohd-linux-x86_64` should work with the Python dependencies.
*   **IoTDB Schema:** The `panel_app.py` typically attempts to create the necessary database and time series schema in IoTDB automatically. If you encounter IoTDB errors related to schema or storage groups, you might need to manually clear IoTDB's data directory (`iotdb/data`) and restart it, or use IoTDB's CLI to inspect/create schema.
