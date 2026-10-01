param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("status", "on", "off", "list", "connect", "disconnect")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [string]$DeviceName = ""
)

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }[0]

    function AwaitOp($op, $t) {
        $netTask = $asTaskGeneric.MakeGenericMethod($t).Invoke($null, @($op))
        $netTask.Wait(-1) | Out-Null
        return $netTask.Result
    }

    [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.BluetoothLEDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.BluetoothCacheMode, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Bluetooth.GenericAttributeProfile.GattDeviceServicesResult, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null

    $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
    $btRadio = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth } | Select-Object -First 1

    if (-not $btRadio) {
        $result = @{
            success = $false
            state = "None"
            error = "No Bluetooth radio adapter found on this system."
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

    $currState = $btRadio.State.ToString()

    if ($Action -eq "status") {
        $result = @{
            success = $true
            state = $currState
            name = $btRadio.Name
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

    if ($Action -eq "on") {
        if ($currState -eq "On") {
            $result = @{
                success = $true
                state = "On"
                already = $true
                name = $btRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
        $status = AwaitOp ($btRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus])
        Start-Sleep -Milliseconds 400
        $newState = $btRadio.State.ToString()
        if ($newState -eq "On") {
            $result = @{
                success = $true
                state = "On"
                already = $false
                name = $btRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        } else {
            $result = @{
                success = $false
                state = $newState
                error = "AccessStatus: $status"
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
    }

    if ($Action -eq "off") {
        if ($currState -eq "Off") {
            $result = @{
                success = $true
                state = "Off"
                already = $true
                name = $btRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
        $status = AwaitOp ($btRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::Off)) ([Windows.Devices.Radios.RadioAccessStatus])
        Start-Sleep -Milliseconds 400
        $newState = $btRadio.State.ToString()
        if ($newState -eq "Off") {
            $result = @{
                success = $true
                state = "Off"
                already = $false
                name = $btRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        } else {
            $result = @{
                success = $false
                state = $newState
                error = "AccessStatus: $status"
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
    }

    function Get-AllPairedDevices {
        $pairedList = @()

        # Classic Bluetooth devices
        $classicSelector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromPairingState($true)
        $classicDevs = AwaitOp ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($classicSelector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])
        foreach ($cd in $classicDevs) {
            $btDev = AwaitOp ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($cd.Id)) ([Windows.Devices.Bluetooth.BluetoothDevice])
            $connStatus = if ($btDev) { $btDev.ConnectionStatus.ToString() } else { "Disconnected" }
            $pairedList += @{
                name = $cd.Name
                id = $cd.Id
                connected = ($connStatus -eq "Connected")
                status = $connStatus
                type = "Classic"
            }
        }

        # BLE devices
        $bleSelector = [Windows.Devices.Bluetooth.BluetoothLEDevice]::GetDeviceSelectorFromPairingState($true)
        $bleDevs = AwaitOp ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($bleSelector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])
        $pnpBle = Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue

        foreach ($bd in $bleDevs) {
            # Skip duplicates if already listed under classic
            if ($pairedList | Where-Object { $_.name -eq $bd.Name }) {
                continue
            }
            $pnpMatch = $pnpBle | Where-Object { $_.FriendlyName -eq $bd.Name -and $_.Status -eq "OK" -and $_.Present -eq $true } | Select-Object -First 1
            $isConnected = ($pnpMatch -ne $null)
            $connStatus = if ($isConnected) { "Connected" } else { "Disconnected" }
            $pairedList += @{
                name = $bd.Name
                id = $bd.Id
                connected = $isConnected
                status = $connStatus
                type = "BLE"
            }
        }

        return $pairedList
    }

    if ($Action -eq "list") {
        $devs = Get-AllPairedDevices
        $result = @{
            success = $true
            count = $devs.Count
            devices = $devs
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

    if ($Action -eq "connect") {
        if (-not $DeviceName) {
            $result = @{
                success = $false
                error = "DeviceName parameter is required for connect action."
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        # Ensure radio is on
        if ($currState -ne "On") {
            AwaitOp ($btRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
            Start-Sleep -Milliseconds 400
        }

        $allPaired = Get-AllPairedDevices
        $matched = $allPaired | Where-Object { $_.name -like "*$DeviceName*" } | Select-Object -First 1

        if (-not $matched) {
            $result = @{
                success = $false
                error = "Device '$DeviceName' is not in your paired Bluetooth devices."
                paired_devices = ($allPaired | ForEach-Object { $_.name })
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        if ($matched.connected) {
            $result = @{
                success = $true
                connected = $true
                already = $true
                device = $matched.name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        # Attempt connection via uncached service query
        $targetId = $matched.id
        $targetType = $matched.type

        if ($targetType -eq "Classic") {
            $btDev = AwaitOp ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($targetId)) ([Windows.Devices.Bluetooth.BluetoothDevice])
            if ($btDev) {
                try {
                    AwaitOp ($btDev.GetRfcommServicesAsync([Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached)) ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult]) | Out-Null
                } catch {}
                Start-Sleep -Milliseconds 500
                $finalStatus = $btDev.ConnectionStatus.ToString()
                if ($finalStatus -eq "Connected") {
                    $result = @{
                        success = $true
                        connected = $true
                        already = $false
                        device = $matched.name
                    }
                    Write-Output (ConvertTo-Json $result -Compress)
                    exit 0
                }
            }
        } else {
            $bleDev = AwaitOp ([Windows.Devices.Bluetooth.BluetoothLEDevice]::FromIdAsync($targetId)) ([Windows.Devices.Bluetooth.BluetoothLEDevice])
            if ($bleDev) {
                try {
                    AwaitOp ($bleDev.GetGattServicesAsync([Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached)) ([Windows.Devices.Bluetooth.GenericAttributeProfile.GattDeviceServicesResult]) | Out-Null
                } catch {}
                Start-Sleep -Milliseconds 500
                $finalStatus = $bleDev.ConnectionStatus.ToString()
                if ($finalStatus -eq "Connected") {
                    $result = @{
                        success = $true
                        connected = $true
                        already = $false
                        device = $matched.name
                    }
                    Write-Output (ConvertTo-Json $result -Compress)
                    exit 0
                }
            }
        }

        # If not connected after attempt, report accurately
        $result = @{
            success = $false
            connected = $false
            device = $matched.name
            error = "Device '$($matched.name)' is not reachable. Please ensure it is powered on, in range, and in pairing or connection mode."
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

    if ($Action -eq "disconnect") {
        if (-not $DeviceName) {
            $result = @{
                success = $false
                error = "DeviceName parameter is required for disconnect action."
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        $allPaired = Get-AllPairedDevices
        $matched = $allPaired | Where-Object { $_.name -like "*$DeviceName*" } | Select-Object -First 1

        if (-not $matched) {
            $result = @{
                success = $false
                error = "Device '$DeviceName' is not in your paired Bluetooth devices."
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        if (-not $matched.connected) {
            $result = @{
                success = $true
                connected = $false
                already = $true
                device = $matched.name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }

        # Device is connected, attempt disconnect
        $targetId = $matched.id
        if ($matched.type -eq "Classic") {
            $btDev = AwaitOp ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($targetId)) ([Windows.Devices.Bluetooth.BluetoothDevice])
            if ($btDev) {
                $btDev.Dispose()
            }
        } else {
            $bleDev = AwaitOp ([Windows.Devices.Bluetooth.BluetoothLEDevice]::FromIdAsync($targetId)) ([Windows.Devices.Bluetooth.BluetoothLEDevice])
            if ($bleDev) {
                $bleDev.Dispose()
            }
        }
        Start-Sleep -Milliseconds 400

        $result = @{
            success = $true
            connected = $false
            already = $false
            device = $matched.name
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

} catch {
    $result = @{
        success = $false
        state = "Error"
        error = $_.Exception.Message
    }
    Write-Output (ConvertTo-Json $result -Compress)
    exit 0
}
