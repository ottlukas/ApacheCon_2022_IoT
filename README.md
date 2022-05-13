# READ ME
This is a short Python script to show an end to end connection from Zenoh IoT Protocol to a Panel Dashboard Webapplication, which could run in a Notebook to analyse the incoming IoT Data.

## Prerequisites

Install and execute
1) [Zenoh Installation](https://zenoh.io/docs/getting-started/installation/)

2) [Zenoh First App](https://zenoh.io/docs/getting-started/first-app/)

Adapt the Producer topic to the one in the panel_script py or the other way around. 
- "'/myhome/kitchen/temp'"
Same for the Zenoh Broker
- "'/myhome/**'"

Start zenoh broker:
```zenohd --mem-storage='/myfactory/**' ``` 

3) Install [Panel](https://panel.holoviz.org/getting_started/index.html)

4) Exececute in a Shell / Terminal: 
```panel serve 'panel_script.py' --autoreload --show ``` 






