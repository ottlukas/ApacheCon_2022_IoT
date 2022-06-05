from zenoh import Zenoh, ChangeKind
import time

def listener(change):
    print(">> [Subscription listener] received {:?} for {} : {} with timestamp {}"
          .format(change.kind, change.path,
                  '' if change.value is None else change.value.get_content(), change.timestamp))

if __name__ == "__main__":
    z = Zenoh({'peer': 'tcp/127.0.0.1:7447'})
    w = z.workspace('/')
    results = w.subscribe('/myfactory/machine1/temp', listener)
    time.sleep(10)
