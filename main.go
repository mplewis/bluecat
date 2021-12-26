package main

import (
	"fmt"
	"log"
	"os"
	"time"
)

const scanTimeout = 60 * time.Second

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
	err := adapter.Enable()
	if err != nil {
		log.Panic(err)
	}

	uuids := []bluetooth.UUID{
		parse("af30"),
		// parse("feed"),
	}

	results := make(chan *bluetooth.ScanResult)
	go func() {
		err = adapter.Scan(uuids, func(adapter *bluetooth.Adapter, device bluetooth.ScanResult) {
			results <- &device
		})
		if err != nil {
			log.Panic(err)
		}
	}()

	var result *bluetooth.ScanResult
	fmt.Println("scanning...")
	select {
	case result = <-results:
		break
	case <-time.After(scanTimeout):
		fmt.Println("scan timed out")
		os.Exit(1)
	}
	fmt.Printf("connecting to device: %s: %s\n", result.LocalName(), result.Address.String())

	cp := bluetooth.ConnectionParams{}

	device, err := adapter.Connect(result.Address, cp)
	if err != nil {
		log.Panic(err)
	}
	fmt.Println(device)

	svcs, err := device.DiscoverServices(nil)
	if err != nil {
		log.Panic(err)
	}
	fmt.Println(svcs)
}
