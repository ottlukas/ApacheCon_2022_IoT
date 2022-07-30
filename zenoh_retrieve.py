from zenoh import Zenoh
from iotdb.Session import Session

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    results = w.get('/myfactory/machine1/temp')
    #data = [results[0].path, results[0].value, int(results[0].timestamp.time)]
    # TODO Insert into IoTDB via Python IoTDB API
    ip = "127.0.0.1"
    port_ = "6667"
    username_ = "root"
    password_ = "root"
    session = Session(ip, port_, username_, password_)
    session.open(False)
    #print('  {} : {}'.format(results[0].timestamp.time, results[0].value))
    #print(str(results[0].value.get_content()))
    sql = "INSERT INTO root.myfactory.machine1(timestamp,temperature) values("+str(int(results[0].timestamp.time))+", "+str(results[0].value.get_content())+")"
    print(sql)
    session.execute_non_query_statement(sql)
    result = session.execute_query_statement("SELECT * FROM root.myfactory.machine1")
    # Transform to Pandas Dataset
    df = result.todf()
    session.close()
    print(df)