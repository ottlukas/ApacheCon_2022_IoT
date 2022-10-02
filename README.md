# READ ME
This is a short Python script to show an end to end connection from Zenoh IoT Protocol to a Panel Dashboard Webapplication, which could run in a Notebook to analyse the incoming IoT Data.

## Prerequisites

Install and execute
1) [Zenoh Installation](https://zenoh.io/docs/getting-started/installation/)
    INFO: Zenho upgrade 30 September 2022 and API changed! (This is not yet included here)

2) [Zenoh First App](https://zenoh.io/docs/getting-started/first-app/)

    Adapt the Producer topic to the one in the panel_script py or the other way around. 
    - "'/myhome/kitchen/temp'"
    Same for the Zenoh Broker
    - "'/myhome/**'"

    Start zenoh broker:
    ```
    zenohd --mem-storage='/myfactory/**' 
    ``` 

3) [Apache IoTDB Quickstart](https://iotdb.apache.org/UserGuide/V0.13.x/QuickStart/QuickStart.html)

    Download [Apache IoTDB](https://iotdb.apache.org/Download/)
    ```
    ./sbin/start-server.sh 
    ```
    ```
    ./sbin/start-cli.sh -h 127.0.0.1 -p 6667 -u root -pw root
    ```
    Execute in IoTDB CLI:
    ```
    SET STORAGE GROUP TO root.myfactory
    CREATE TIMESERIES root.myfactory.machine1.temperature WITH DATATYPE=INT32, ENCODING=PLAIN
    INSERT INTO root.myfactory.machine1(timestamp,temperature) values(200,21) // Test Insert
    SELECT * FROM root.myfactory.machine1
    ```

4) Install [Panel](https://panel.holoviz.org/getting_started/index.html)
    
    Used Python packages:
    ```
    import zenoh
    from iotdb.Session import Session
    from datetime import datetime
    import panel as pn
    ```
5) Execute in a Shell / Terminal (whith running Zenoh Broker and Apache IoTDB): 
    ``` 
    panel serve 'panel_script.py' --autoreload --show 
    ``` 






