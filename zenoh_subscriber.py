from zenoh import Zenoh, ChangeKind
import time

def listener(change):
    if change.kind == ChangeKind.PUT:
        print('Publication received: "{}" = "{}"'
                .format(change.path, change.value))

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    results = w.subscribe('/myfactory/machine1/temp', listener)
    time.sleep(10)
