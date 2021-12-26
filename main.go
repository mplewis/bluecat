package main

import (
	"fmt"

	"github.com/mplewis/bluecat/bluetooth"
)

var adapter = bluetooth.DefaultAdapter

func parse(uuid4 string) bluetooth.UUID {
	uuid128 := fmt.Sprintf("0000%s-0000-1000-8000-00805f9b34fb", uuid4)
	uuid, err := bluetooth.ParseUUID(uuid128)
	if err != nil {
		panic(err)
	}
	return uuid
}

func main() {
	must("enable BLE stack", adapter.Enable())

	uuids := []bluetooth.UUID{
		parse("af30"),
	}

	println("scanning...")
	err := adapter.Scan(uuids, func(adapter *bluetooth.Adapter, device bluetooth.ScanResult) {
		println("found device:", device.Address.String(), device.RSSI, device.LocalName())
	})
	must("start scan", err)
}

func must(action string, err error) {
	if err != nil {
		panic("failed to " + action + ": " + err.Error())
	}
}
