package main

import (
	"fmt"
	"log"

	"github.com/mplewis/bluecat/bluetooth"
)

var adapter = bluetooth.DefaultAdapter

func parse(uuid4 string) bluetooth.UUID {
	uuid128 := fmt.Sprintf("0000%s-0000-1000-8000-00805f9b34fb", uuid4)
	uuid, err := bluetooth.ParseUUID(uuid128)
	if err != nil {
		log.Panic(err)
	}
	return uuid
}

func main() {
	fmt.Println(checksum([]byte("deadbeef")))

	err := adapter.Enable()
	if err != nil {
		log.Panic(err)
	}

	uuids := []bluetooth.UUID{
		parse("af30"),
	}

	println("scanning...")
	err = adapter.Scan(uuids, func(adapter *bluetooth.Adapter, device bluetooth.ScanResult) {
		println("found device:", device.Address.String(), device.RSSI, device.LocalName())
	})
	if err != nil {
		log.Panic(err)
	}
}
