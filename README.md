# ApacheCon 2022 IoT Demo: Zenoh, Apache IoTDB & Panel

This repository demonstrates an end-to-end, production-like IoT telemetry ingestion and visualization pipeline. It features a distributed architecture powered by **Eclipse Zenoh**, **Apache IoTDB**, and a **Panel + FastAPI** dashboard, all orchestrated via Docker Compose.

---

## Project Overview

The objective of this demo is to showcase how high-throughput sensor telemetry can be collected, bridged to a time-series database, and visualized in real-time.

- **Zenoh Broker Container**: Connects the simulator, the database bridge, and the web portal.
- **Zenoh-to-IoTDB Bridge Container**: Subscribes to the live Zenoh topic, validates incoming JSON data using Pydantic, and persists telemetry in Apache IoTDB.
- **Apache IoTDB Container**: Stores the time-series data.
- **FastAPI + Panel Dashboard Container**: 
  - Hosts the sensor simulator (as a subprocess) 
  - Serves the monitoring UI at `http://localhost:8080/panel`
  - Provides APIs to start/stop the simulator
  - Visualizes metrics through two logically independent widgets:
    1. A real-time gauge and line chart receiving data directly from Zenoh.
    2. A bar chart updating periodically by querying historical data from Apache IoTDB.
- **User**: Accesses the dashboard via a browser.

---

## Architecture Diagram

```mermaid
flowchart LR
    subgraph DashboardContainer[Dashboard Container (iot-dashboard)]
        Simulator[Sensor Simulator]:::internal
        Dashboard[Panel + FastAPI Dashboard]:::internal
    end
    Zenoh[Zenoh Broker Container (zenoh-broker)]:::external
    IoTDB[Apache IoTDB Container (iotdb-db)]:::external
    Bridge[Zenoh-to-IoTDB Bridge Container (zenoh-iotdb-bridge)]:::external
    User[Browser]:::external
    
    Simulator -->|Zenoh publish tcp/zenoh:7447| Zenoh
    Zenoh -->|subscribe| Bridge
    Bridge -->|insert timeseries| IoTDB
    Dashboard -->|subscribe live data| Zenoh
    Dashboard -->|query historical data| IoTDB
    User -->|http://localhost:8080/panel| Dashboard
    
    classDef internal fill:#f9f,stroke:#333,stroke-width:1px;
    classDef external fill:#bbf,stroke:#333,stroke-width:1px;
```

---

## Prerequisites

- **Docker** and **Docker Compose v2** (or Docker Desktop on Windows/macOS)
  - Linux: Install [Docker Engine](https://docs.docker.com/engine/install/) and [Docker Compose plugin](https://docs.docker.com/compose/install/)
  - Windows/macOS: Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- (Optional) For running simulator/dashboard on host instead of containers:
  - Python 3.11+ or 3.12+
  - pip and venv python tools

---

## Quick Start (Using Docker Compose)

Follow these steps to run the complete environment using Docker Compose:

1. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env if needed to customize ports, credentials, etc.
   ```

2. **Start All Services**:
   ```bash
   docker compose up -d
   ```
   This starts the Zenoh broker, Apache IoTDB, the ingestion bridge, and the dashboard container.
   - The dashboard container includes the sensor simulator (as a subprocess) and the web dashboard.
   - Containers start in detached mode (`-d`).

3. **Start the Sensor Simulator**:
   The simulator runs inside the dashboard container. Start it via the dashboard's API:
   ```bash
   curl -X POST http://localhost:8080/api/simulator/start
   ```
   *Alternative*: Use the dashboard UI if it provides a start/stop button (check the UI).

4. **Open the Dashboard**:
   Navigate to the portal in your browser:
   [http://localhost:8080/panel](http://localhost:8080/panel)

---

## Project Structure

```
ApacheCon_2022_IoT/
├── .env.example          # Template environment variables
├── .gitignore
├── docker-compose.yml    # Defines all services (zenoh, iotdb, zenoh-to-iotdb, dashboard)
├── Dockerfile.bridge     # Builds the Zenoh-to-IoTDB bridge
├── Dockerfile.dashboard  # Builds the dashboard container (includes simulator & dashboard)
├── app/
│   ├── dashboard.py      # FastAPI + Panel application entrypoint
│   └── ...               # Other application files
├── scripts/
│   └── sensor_simulator.py # Telemetry simulator script
├── requirements-dev.txt  # Python dependencies for development
├── requirements.txt      # Python dependencies for runtime
└── tests/                # Test suites
```

---

## Configuration

The project uses environment variables defined in `.env` (copied from `.env.example`). Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ZENOH_KEY_EXPRESSION` | Zenoh key expression for telemetry | `myfactory/machine1/temperature` |
| `IOTDB_HOST` | IoTDB hostname (service name in compose) | `iotdb` |
| `IOTDB_PORT` | IoTDB Thrift RPC port | `6667` |
| `IOTDB_USER` | IoTDB username | `root` |
| `IOTDB_PASSWORD` | IoTDB password | `root` |
| `IOTDB_DATABASE` | IoTDB database namespace | `root.myfactory` |
| `IOTDB_DEVICE` | IoTDB device path | `root.myfactory.machine1` |
| `IOTDB_MEASUREMENT` | IoTDB measurement name | `temperature` |
| `DASHBOARD_PORT` | Host port for dashboard | `8080` |
| `SIMULATOR_INTERVAL_SECONDS` | Simulator publish interval (seconds) | `1` |
| `SIMULATOR_MIN_VALUE` | Simulated min temperature | `15` |
| `SIMULATOR_MAX_VALUE` | Simulated max temperature | `35` |

To customize, edit `.env` before running `docker compose up`.

---

## Running the Project

### Using Docker Compose (Recommended)

Follow the [Quick Start](#quick-start-using-docker-compose) steps above.

### Running Simulator and Dashboard on Host (Alternative)

If you prefer to run the simulator and dashboard on your host machine (while still using Docker Compose for Zenoh, IoTDB, and the bridge):

1. Start the infrastructure services:
   ```bash
   docker compose up -d zenoh iotdb zenoh-to-iotdb
   ```

2. Prepare your Python environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

3. Start the sensor simulator:
   ```bash
   python zenoh_producer.py
   ```

4. Start the Panel dashboard:
   ```bash
   panel serve panel_script.py --autoreload --show
   ```
   This opens the dashboard at [http://localhost:5006/panel_script](http://localhost:5006/panel_script).

> **Note**: The host-based method requires Python dependencies and is provided for development/debugging. The Docker Compose method is recommended for consistency.

---

## Troubleshooting

### Common Issues on Linux

- **Docker daemon not running**: Start with `sudo systemctl start docker`
- **Permission denied**: Add your user to the `docker` group: `sudo usermod -aG docker $USER` (requires relogin)
- **Port already in use**: Check what's using ports 7447, 8000, 6667, 8080 with `sudo ss -tlnp` and stop conflicting services
- **Slow IoTDB startup**: Apache IoTDB takes 15-20 seconds to initialize. The health check in `docker-compose.yml` accounts for this.
- **Empty dashboards**: 
  - Verify simulator is running: `curl -X POST http://localhost:8080/api/simulator/status`
  - Check bridge logs: `docker compose logs -f zenoh-iotdb-bridge`
  - Verify Zenoh connection: simulator must use `tcp/zenoh:7447` (not localhost)

### Common Issues on Windows (Docker Desktop)

- **Docker Desktop not running**: Launch Docker Desktop application and wait for it to initialize
- **WSL 2 backend issues**: Ensure WSL 2 is installed and set as default in Docker Desktop Settings > Resources > WSL Integration
- **Firewall blocking ports**: Allow Docker through Windows Defender Firewall
- **Volume permission issues**: 
  - Right-click Docker Desktop > Settings > Resources > File Sharing
  - Ensure your project drive (e.g., C:) is shared
  - Alternatively, use WSL 2 paths (e.g., `\\wsl$\Ubuntu\home\user\project`)
- **Container startup slow**: Increase Docker Desktop's memory/CPU allocation in Settings > Resources
- **localhost not working**: Try `http://host.docker.internal:8080/panel` if using Docker Desktop for Mac/Windows with specific network configurations

### General Troubleshooting Steps

1. **Check container status**:
   ```bash
   docker compose ps
   ```
   All services should show `State: Up`

2. **View logs**:
   ```bash
   docker compose logs -f  # Follow all logs
   docker compose logs -f zenoh-iotdb-bridge  # Specific service
   ```

3. **Restart services**:
   ```bash
   docker compose restart
   ```

4. **Reset everything** (WARNING: deletes all data):
   ```bash
   docker compose down -v
   docker compose up -d
   ```

5. **Verify simulator is publishing**:
   ```bash
   # Inside dashboard container:
   docker compose exec dashboard python -c "import time; time.sleep(2); print('Simulator status:'); !curl -s http://localhost:8080/api/simulator/status"
   ```

---

## Updating the Project

After making changes to the code or Dockerfiles, rebuild and restart the affected services:

```bash
# Rebuild all services and restart
docker compose up -d --build

# Or rebuild specific services (e.g., after changing dashboard code)
docker compose build dashboard
docker compose up -d dashboard
```

If you modified Python dependencies, rebuild the dashboard container:
```bash
docker compose build --no-cache dashboard
docker compose up -d dashboard
```

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

Please ensure your code follows the existing style and includes tests where applicable.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*ApacheCon 2022 IoT Demo: Zenoh, Apache IoTDB & Panel*