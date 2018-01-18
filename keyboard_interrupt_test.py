import time
def test():
    i = 0
    while True:
        try:
            print i
            i += 1
            time.sleep(1)
            
        except KeyboardInterrupt:
            print "interrupted by keyboard"
            return 1

if __name__ == "__main__":
    main = test()
