param (
    [Parameter(Mandatory=$true)]
    [ValidateSet("status", "on", "off")]
    [string]$Action
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
    $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])

    $wifiRadio = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi } | Select-Object -First 1

    if (-not $wifiRadio) {
        $result = @{
            success = $false
            state = "None"
            error = "No Wi-Fi radio adapter found on this system."
        }
        Write-Output (ConvertTo-Json $result -Compress)
        exit 0
    }

    $currState = $wifiRadio.State.ToString()

    if ($Action -eq "status") {
        $result = @{
            success = $true
            state = $currState
            name = $wifiRadio.Name
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
                name = $wifiRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
        $status = AwaitOp ($wifiRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::On)) ([Windows.Devices.Radios.RadioAccessStatus])
        Start-Sleep -Milliseconds 400
        $newState = $wifiRadio.State.ToString()
        if ($newState -eq "On") {
            $result = @{
                success = $true
                state = "On"
                already = $false
                name = $wifiRadio.Name
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
                name = $wifiRadio.Name
            }
            Write-Output (ConvertTo-Json $result -Compress)
            exit 0
        }
        $status = AwaitOp ($wifiRadio.SetStateAsync([Windows.Devices.Radios.RadioState]::Off)) ([Windows.Devices.Radios.RadioAccessStatus])
        Start-Sleep -Milliseconds 400
        $newState = $wifiRadio.State.ToString()
        if ($newState -eq "Off") {
            $result = @{
                success = $true
                state = "Off"
                already = $false
                name = $wifiRadio.Name
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
} catch {
    $result = @{
        success = $false
        state = "Error"
        error = $_.Exception.Message
    }
    Write-Output (ConvertTo-Json $result -Compress)
    exit 0
}
