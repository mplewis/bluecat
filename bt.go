package main

import (
	"github.com/JuulLabs-OSS/cbgo"
	"github.com/rs/zerolog/log"
)

type Delegate struct {
	cbgo.CentralManagerDelegateBase
	cbgo.PeripheralDelegateBase
}

func (d *Delegate) CentralManagerDidUpdateState(c cbgo.CentralManager) {
	log.Debug().Msg("")
	if cmgr.State() == cbgo.ManagerStatePoweredOn {
		d.connectToPrinter()
	}
}
