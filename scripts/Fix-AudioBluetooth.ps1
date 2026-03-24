param(
    [string[]]$DeviceKeywords = @("Soundcore", "Q45"),
    [string]$LogPath = $(Join-Path (Split-Path -Parent $PSScriptRoot) "log.txt"),
    [int]$AdapterRestartDelaySeconds = 4
)

$ErrorActionPreference = "Continue"
$script:FailedSteps = 0

function Write-Log {
    param(
        [ValidateSet("INFO", "WARNING", "ERROR")]
        [string]$Level = "INFO",
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Write-Host $line

    try {
        $directory = Split-Path -Parent $LogPath
        if ($directory -and -not (Test-Path -LiteralPath $directory)) {
            New-Item -ItemType Directory -Path $directory -Force | Out-Null
        }

        Add-Content -Path $LogPath -Value $line -Encoding UTF8
    }
    catch {
        Write-Host ("[{0}] [WARNING] No se pudo escribir en el log: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $_.Exception.Message)
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Log -Level "INFO" -Message ("START - {0}" -f $Name)

    try {
        & $Action
        Write-Log -Level "INFO" -Message ("DONE - {0}" -f $Name)
    }
    catch {
        $script:FailedSteps++
        Write-Log -Level "ERROR" -Message ("FAIL - {0}: {1}" -f $Name, $_.Exception.Message)
    }
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-KeywordPattern {
    param([string[]]$Keywords)

    $escaped = @()

    foreach ($keyword in $Keywords) {
        if (-not [string]::IsNullOrWhiteSpace($keyword)) {
            $escaped += [Regex]::Escape($keyword.Trim())
        }
    }

    if ($escaped.Count -eq 0) {
        return ".*"
    }

    return "(?i)(" + ($escaped -join "|") + ")"
}

function Get-DeviceLabel {
    param([Parameter(Mandatory = $true)]$Device)

    if ($Device.PSObject.Properties.Match("FriendlyName").Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($Device.FriendlyName)) {
        return $Device.FriendlyName
    }

    if ($Device.PSObject.Properties.Match("Name").Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($Device.Name)) {
        return $Device.Name
    }

    if ($Device.PSObject.Properties.Match("Caption").Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($Device.Caption)) {
        return $Device.Caption
    }

    if ($Device.PSObject.Properties.Match("InstanceId").Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($Device.InstanceId)) {
        return $Device.InstanceId
    }

    if ($Device.PSObject.Properties.Match("PNPDeviceID").Count -gt 0 -and -not [string]::IsNullOrWhiteSpace($Device.PNPDeviceID)) {
        return $Device.PNPDeviceID
    }

    return "Unknown device"
}

function Wait-ServiceState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$State,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    do {
        $service = Get-Service -Name $Name -ErrorAction Stop
        if ($service.Status.ToString() -eq $State) {
            return $true
        }

        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Wait-ProcessState {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [ValidateSet("Running", "Stopped")]
        [string]$State = "Running",
        [int]$TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    do {
        $process = Get-Process -Name $Name -ErrorAction SilentlyContinue
        $isRunning = $null -ne $process

        if ($State -eq "Running" -and $isRunning) {
            return $true
        }

        if ($State -eq "Stopped" -and -not $isRunning) {
            return $true
        }

        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Restart-ServiceSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ServiceName,
        [Parameter(Mandatory = $true)]
        [string]$DisplayName
    )

    $service = Get-Service -Name $ServiceName -ErrorAction Stop

    if ($service.Status -eq "Stopped") {
        Start-Service -Name $ServiceName -ErrorAction Stop
    }
    else {
        Restart-Service -Name $ServiceName -Force -ErrorAction Stop
    }

    if (-not (Wait-ServiceState -Name $ServiceName -State "Running" -TimeoutSeconds 20)) {
        throw ("{0} no alcanzó estado Running a tiempo." -f $DisplayName)
    }

    Write-Log -Level "INFO" -Message ("{0} reiniciado y en estado Running." -f $DisplayName)
}

function Get-BluetoothAdapters {
    $devices = Get-PnpDevice -Class Bluetooth -ErrorAction Stop

    return $devices | Where-Object {
        $_.InstanceId -notlike "BTHENUM*" -and
        $_.InstanceId -notlike "SWD\\*" -and
        (Get-DeviceLabel $_) -notmatch "(?i)enumerator|radio management|personal area network|device \(personal area network\)|rfcomm"
    }
}

function Restart-BluetoothAdapters {
    $adapters = Get-BluetoothAdapters

    if (-not $adapters) {
        throw "No se detectó ningún adaptador Bluetooth físico para reiniciar."
    }

    $restarted = 0

    foreach ($adapter in $adapters) {
        $name = Get-DeviceLabel $adapter

        try {
            Write-Log -Level "INFO" -Message ("Reiniciando adaptador Bluetooth: {0} [{1}]" -f $name, $adapter.InstanceId)
            Disable-PnpDevice -InstanceId $adapter.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null
            Start-Sleep -Seconds $AdapterRestartDelaySeconds
            Enable-PnpDevice -InstanceId $adapter.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null
            $restarted++
        }
        catch {
            Write-Log -Level "WARNING" -Message ("No se pudo reiniciar el adaptador {0}: {1}" -f $name, $_.Exception.Message)
        }
    }

    if ($restarted -eq 0) {
        throw "No se pudo reiniciar ningún adaptador Bluetooth."
    }

    & pnputil /scan-devices | Out-Null
    Start-Sleep -Seconds 3
}

function Remove-GhostAudioEndpoints {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPattern
    )

    $ghosts = Get-CimInstance Win32_PnPEntity -ErrorAction Stop | Where-Object {
        $_.PNPClass -eq "AudioEndpoint" -and
        $_.Name -match $TargetPattern -and
        (
            $_.ConfigManagerErrorCode -eq 24 -or
            ($_.Status -and $_.Status -ne "OK") -or
            ($_.PSObject.Properties.Match("Present").Count -gt 0 -and -not $_.Present)
        )
    }

    if (-not $ghosts) {
        Write-Log -Level "INFO" -Message "No se encontraron AudioEndpoint fantasma para los audífonos objetivo."
        return
    }

    foreach ($ghost in $ghosts) {
        $name = Get-DeviceLabel $ghost

        try {
            Write-Log -Level "INFO" -Message ("Eliminando endpoint fantasma: {0} [{1}]" -f $name, $ghost.PNPDeviceID)
            $output = & pnputil /remove-device "$($ghost.PNPDeviceID)" 2>&1
            foreach ($line in $output) {
                if (-not [string]::IsNullOrWhiteSpace($line)) {
                    Write-Log -Level "INFO" -Message ("pnputil: {0}" -f $line.Trim())
                }
            }
        }
        catch {
            Write-Log -Level "WARNING" -Message ("No se pudo eliminar el endpoint fantasma {0}: {1}" -f $name, $_.Exception.Message)
        }
    }

    & pnputil /scan-devices | Out-Null
}

function Force-StereoProfile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPattern
    )

    $handsFreePattern = "(?i)hands[- ]?free|ag audio|headset"
    $stereoPattern = "(?i)stereo|a2dp|headphones"

    $allDevices = Get-PnpDevice -ErrorAction Stop
    $handsFreeDevices = $allDevices | Where-Object {
        $label = Get-DeviceLabel $_
        $label -match $TargetPattern -and $label -match $handsFreePattern
    }
    $stereoDevices = $allDevices | Where-Object {
        $label = Get-DeviceLabel $_
        $label -match $TargetPattern -and $label -match $stereoPattern
    }

    if ($handsFreeDevices) {
        foreach ($device in $handsFreeDevices) {
            $name = Get-DeviceLabel $device

            try {
                Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null
                Write-Log -Level "INFO" -Message ("Endpoint Hands-Free deshabilitado para favorecer Stereo: {0}" -f $name)
            }
            catch {
                Write-Log -Level "WARNING" -Message ("No se pudo deshabilitar el endpoint Hands-Free {0}: {1}" -f $name, $_.Exception.Message)
            }
        }
    }
    else {
        Write-Log -Level "WARNING" -Message "No se detectaron endpoints Hands-Free del dispositivo para deshabilitar."
    }

    if ($stereoDevices) {
        foreach ($device in $stereoDevices) {
            $name = Get-DeviceLabel $device

            try {
                if ($device.Status -ne "OK") {
                    Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false -ErrorAction Stop | Out-Null
                }

                Write-Log -Level "INFO" -Message ("Endpoint Stereo conservado o habilitado: {0}" -f $name)
            }
            catch {
                Write-Log -Level "WARNING" -Message ("No se pudo habilitar o verificar el endpoint Stereo {0}: {1}" -f $name, $_.Exception.Message)
            }
        }
    }
    else {
        Write-Log -Level "WARNING" -Message "No se detectó explícitamente un endpoint Stereo; Windows deberá renegociar A2DP al reconectar."
    }
}

Write-Log -Level "INFO" -Message "Bluetooth Audio Resetter iniciado."
Write-Log -Level "INFO" -Message ("Keywords objetivo: {0}" -f ($DeviceKeywords -join ", "))
Write-Log -Level "INFO" -Message ("Archivo de log: {0}" -f $LogPath)

if (-not (Test-IsAdministrator)) {
    Write-Log -Level "WARNING" -Message "El script no se está ejecutando como administrador. Algunas acciones pueden fallar."
}

try {
    Import-Module PnpDevice -ErrorAction Stop
    Write-Log -Level "INFO" -Message "Módulo PnpDevice cargado correctamente."
}
catch {
    Write-Log -Level "WARNING" -Message ("No se pudo cargar PnpDevice. Las operaciones PnP podrían fallar: {0}" -f $_.Exception.Message)
}

$targetPattern = Get-KeywordPattern -Keywords $DeviceKeywords

Invoke-Step -Name "Reiniciar servicio Windows Audio (audiosrv)" -Action {
    Restart-ServiceSafe -ServiceName "audiosrv" -DisplayName "Windows Audio"
}

Invoke-Step -Name "Reiniciar servicio Bluetooth Support Service (bthserv)" -Action {
    Restart-ServiceSafe -ServiceName "bthserv" -DisplayName "Bluetooth Support Service"
}

Invoke-Step -Name "Finalizar y reactivar audiodg.exe" -Action {
    $processes = Get-Process -Name "audiodg" -ErrorAction SilentlyContinue

    if ($processes) {
        $processes | Stop-Process -Force -ErrorAction Stop
        Write-Log -Level "INFO" -Message "audiodg.exe finalizado."
        [void](Wait-ProcessState -Name "audiodg" -State "Stopped" -TimeoutSeconds 10)
    }
    else {
        Write-Log -Level "WARNING" -Message "audiodg.exe no estaba en ejecución al iniciar el paso."
    }

    Restart-ServiceSafe -ServiceName "audiosrv" -DisplayName "Windows Audio"

    if (-not (Wait-ProcessState -Name "audiodg" -State "Running" -TimeoutSeconds 15)) {
        throw "audiodg.exe no reapareció después de reiniciar Windows Audio."
    }

    Write-Log -Level "INFO" -Message "audiodg.exe reapareció correctamente."
}

Invoke-Step -Name "Reiniciar adaptador Bluetooth vía PnP" -Action {
    Restart-BluetoothAdapters
}

Invoke-Step -Name "Eliminar dispositivos fantasma AudioEndpoint" -Action {
    Remove-GhostAudioEndpoints -TargetPattern $targetPattern
}

Invoke-Step -Name "Forzar perfil Stereo sobre Hands-Free (best effort)" -Action {
    Force-StereoProfile -TargetPattern $targetPattern
}

Invoke-Step -Name "Escanear de nuevo el hardware PnP" -Action {
    & pnputil /scan-devices | Out-Null
    Write-Log -Level "INFO" -Message "Escaneo PnP completado."
}

if ($script:FailedSteps -gt 0) {
    Write-Log -Level "WARNING" -Message ("Proceso completado con {0} paso(s) fallido(s). Revisar log.txt para más detalle." -f $script:FailedSteps)
    exit 1
}

Write-Log -Level "INFO" -Message "Proceso completado correctamente."
exit 0
