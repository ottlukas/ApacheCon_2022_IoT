# ApacheCon 2022 IoT Demo

This repository contains the code for an IoT demo showcasing integration with Apache IoTDB and Zenoh for data ingestion and visualization/control via a Python Panel application.

This `feature/zenoh-api-upgrade` branch specifically focuses on upgrading the Zenoh API to the latest stable version and providing a Dockerized deployment.

## Architecture

The demo consists of three main components:

1.  **Zenoh Router (`zenohd`):** The core communication middleware enabling efficient data distribution.
2.  **Apache IoTDB:** A high-performance time-series database optimized for IoT data.
3.  **Panel Service (Python):** An application built with [Panel](https://panel.holoviz.org/) that interacts with Zenoh to send/receive data, and with IoTDB to store and retrieve time-series data. It also provides a web-based UI for visualization.

## Prerequisites

To run this demo, you will need:

*   [Docker and Docker Compose](https://docs.docker.com/get-docker/) (Recommended for easy setup)
*   [Python 3.9+](https://www.python.org/downloads/) (if you wish to run or develop the Panel service outside of Docker)
*   [Java 8 or higher](https://www.java.com/download/) (Only if running IoTDB directly without Docker)
*   Git (for cloning the repository)

## Deployment and Running Instructions

The recommended method for deploying and running the services is using Docker Compose. This simplifies setup by running all services in isolated Docker containers.

### Method 1: Using Docker Compose (Recommended)

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/ottlukas/ApacheCon_2022_IoT.git
    cd ApacheCon_2022_IoT
    # If you are not already on it, checkout the correct branch:
    # git checkout feature/zenoh-api-upgrade 
    ```

2.  **Ensure Docker and Docker Compose are Installed:**
    Follow the official Docker installation guides for your operating system.

3.  **Project Structure for Panel Service:**
    The Panel service code is located in the `panel/` directory.
    *   `panel/panel_app.py`: The main Python script for the Panel application.
    *   `panel/requirements.txt`: Python dependencies for the Panel application.
    *   `panel/asf-estd-1999-logo.jpg`: Image asset used by the application.

    The `Dockerfile.panel` at the root of the project is used to build the Panel service Docker image.
    The `docker-compose.yml` at the root orchestrates all services.

4.  **Start the Services:**
    Navigate to the root of your `ApacheCon_2022_IoT` repository (where `docker-compose.yml` is located) and run:
    ```bash
    docker compose up -d
    ```
    This command will:
    *   Download the necessary base images for Zenoh and IoTDB if not already present.
    *   Build the Docker image for the `panel` service using `Dockerfile.panel`.
    *   Start the `zenohd`, `iotdb`, and `panel` services in detached mode (`-d`).

5.  **Verify Services:**
    *   Check container status: `docker ps`
        (You should see `zenohd`, `iotdb`, and `panel` containers running).
    *   View logs for all services: `docker compose logs -f`
    *   View logs for a specific service: `docker compose logs -f panel` (or `zenohd`, `iotdb`)
    *   Access the Panel UI: The `panel_app.py` script (as provided in the original repository) runs a Panel server. By default, Panel serves applications on port 5006. If you want to access it, you would add `ports: - "5006:5006"` to the `panel` service definition in `docker-compose.yml`. (Note: The provided `docker-compose.yml` in the issue did not include this port mapping for the panel service, but it's a common requirement for web UIs).

6.  **Interacting with the System:**
    *   **Zenoh Producer/Subscriber (Optional, for testing):** You can run the `zenoh_producer.py` or `zenoh_subscriber.py` scripts from the project root on your host machine (ensure `eclipse-zenoh` is installed locally via pip). They are configured to connect to `tcp/127.0.0.1:7447`, which is exposed by the `zenohd` Docker container.
        ```bash
        # In one terminal
        python zenoh_producer.py 
        # In another terminal
        python zenoh_subscriber.py
        ```
    *   **IoTDB Data:** The `panel_app.py` (via `zenoh_retrieve.py`'s logic which it incorporates) should be storing data into IoTDB. You can verify this using an IoTDB client or by observing the Panel UI if it displays this data.

7.  **Stop Services:**
    To stop and remove all containers, networks, and volumes (if any were configured to persist) defined in the `docker-compose.yml`:
    ```bash
    docker compose down
    ```

### Method 2: Running Services via Command Line (Advanced)

This method requires manual installation and management of each component on your host machine. Please refer to the official documentation for Zenoh, Apache IoTDB, and Panel for detailed installation instructions.

1.  **Start Zenoh Router (`zenohd`):**
    *   Install Zenoh (e.g., `pip install eclipse-zenoh` and ensure `zenohd` is in your PATH, or download binaries).
    *   Run: `zenohd`

2.  **Start Apache IoTDB:**
    *   Download and configure Apache IoTDB.
    *   Run: `./sbin/start-server.sh` (from your IoTDB directory).

3.  **Run Panel Service (Python):**
    *   Navigate to the `panel/` directory.
    *   Install dependencies: `pip install -r requirements.txt`
    *   Ensure environment variables `ZENOH_ROUTER_ENDPOINT`, `IOTDB_HOST`, `IOTDB_PORT` are set if you are not using the defaults, or modify `panel_app.py` accordingly.
    *   Run: `panel serve panel_app.py --show`

## Code Quality
The Python code in this repository has been formatted and linted using Pylint where applicable to ensure adherence to common Python coding standards and improve readability.

---
*This README has been updated to reflect the Dockerized deployment and recent API upgrades.*
