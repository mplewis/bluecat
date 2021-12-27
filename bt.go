package main

import (
	"fmt"

	"tinygo.org/x/bluetooth"
)

func withConn(names []string, cb func(*bluetooth.Device, error)) {
	adapter := bluetooth.DefaultAdapter
	err := adapter.Enable()
	if err != nil {
		cb(nil, err)
		return
	}

	ch := make(chan bluetooth.ScanResult)
	go func() {
		err = adapter.Scan(func(_ *bluetooth.Adapter, device bluetooth.ScanResult) {
			for _, name := range names {
				if device.LocalName() == name {
					ch <- device
					return
				}
			}
		})
		if err != nil {
			cb(nil, err)
		}
	}()

	// TODO: timeout
	result := <-ch

	device, err := adapter.Connect(result.Address, bluetooth.ConnectionParams{})
	connected := err == nil
	defer func() {
		if !connected {
			return
		}
		err = device.Disconnect()
		if err != nil {
			fmt.Println(err)
		}
	}()

	cb(device, err)
}
