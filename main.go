package main

import (
	"fmt"
	"log"

	"tinygo.org/x/bluetooth"
)

var printerNames = []string{
	"GT01",
	"GB01",
	"GB02",
	"GB03",
}

var adapter = bluetooth.DefaultAdapter

func main() {
	err := adapter.Enable()
	if err != nil {
		log.Panic(err)
	}

	println("scanning...")
	ch := make(chan bluetooth.ScanResult)
	go func() {
		err = adapter.Scan(func(adapter *bluetooth.Adapter, device bluetooth.ScanResult) {
			for _, name := range printerNames {
				if device.LocalName() == name {
					ch <- device
					return
				}
			}
		})
		if err != nil {
			log.Panic(err)
		}
	}()

	result := <-ch
	fmt.Printf("found printer: %s\n", result.LocalName())

	device, err := adapter.Connect(result.Address, bluetooth.ConnectionParams{})
	if err != nil {
		log.Panic(err)
	}

	svcs, err := device.DiscoverServices(nil)
	if err != nil {
		log.Panic(err)
	}

	fmt.Println(svcs)

	err = device.Disconnect()
	if err != nil {
		log.Panic(err)
	}
}
