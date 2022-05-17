from zenoh import Zenoh

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    results = w.get('/myfactory/machine1/temp')
    key, value = results[0].path, results[0].value
    print('  {} : {}'.format(key, value))