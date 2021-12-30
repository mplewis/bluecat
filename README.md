# Bluecat

A Python-based server for printing to a cute cat printer.

# Usage

Start the server using Docker:

```sh
docker build -t bluecat .

docker run \
    -v /var/run/dbus:/var/run/dbus \  # connect to local DBus/BlueZ
    --privileged \                    # ...with enough permission to use it
    -p 8000:8000 \                    # serve on port 8000
    -it bluecat
```

Send an image using [HTTPie](https://httpie.io/):

```
http post --form localhost:8000/print image@/path/to/cute_kitty.jpg
```

# Why Python?

I do not like working in Python. I find myself constantly fighting it for any tasks of any asynchronicity. I resent its lack of type safety.

However, I was having issues on my Linux machine with the [TinyGo Bluetooth](https://github.com/tinygo-org/bluetooth) project. I was not able to reliably connect to a device and print an image.

I hope to revisit the TinyGo Bluetooth project when it is more mature, and I hope to contribute to help it get there. In the meantime, [Bleak](https://github.com/hbldh/bleak) seems to provide the most reliable cross-platform interface in a language I write.
