package main

import (
	"fmt"
	"log"
	"os"
	"time"

	"github.com/mplewis/bluecat/bluetooth"
)

const scanTimeout = 15 * time.Second

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
	}

	results := make(chan *bluetooth.ScanResult)
	fmt.Println("starting scan")

	go func() {
		err = adapter.Scan(uuids, func(adapter *bluetooth.Adapter, device bluetooth.ScanResult) {
			results <- &device
		})
		if err != nil {
			log.Panic(err)
		}
	}()

	var device *bluetooth.ScanResult
	fmt.Println("scanning...")
	select {
	case device = <-results:
		fmt.Printf("found device: %s\n", device.LocalName())
	case <-time.After(scanTimeout):
		fmt.Println("scan timed out")
		os.Exit(1)
	}
}
