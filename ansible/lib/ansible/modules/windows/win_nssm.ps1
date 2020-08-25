#!powershell
# This file is part of Ansible
#
# Copyright 2015, George Frank <george@georgefrank.net>
# Copyright 2015, Adam Keech <akeech@chathamfinancial.com>
# Copyright 2015, Hans-Joachim Kliemeck <git@kliemeck.de>
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

$ErrorActionPreference = "Stop"

# WANT_JSON
# POWERSHELL_COMMON

$params = Parse-Args $args

$result = @{
    changed = $false
}

$name = Get-AnsibleParam -obj $params -name "name" -type "str" -failifempty $true
$state = Get-AnsibleParam -obj $params -name "state" -type "str" -default "present" -validateset "present","absent","started","stopped","restarted" -resultobj $result

$application = Get-AnsibleParam -obj $params -name "application" -type "str"
$appParameters = Get-AnsibleParam -obj $params -name "app_parameters" -type "str"
$appParametersFree  = Get-AnsibleParam -obj $params -name "app_parameters_free_form" -type "str"
$startMode = Get-AnsibleParam -obj $params -name "start_mode" -type "str" -default "auto" -validateset "auto","manual","disabled" -resultobj $result

$stdoutFile = Get-AnsibleParam -obj $params -name "stdout_file" -type "str"
$stderrFile = Get-AnsibleParam -obj $params -name "stderr_file" -type "str"
$dependencies = Get-AnsibleParam -obj $params -name "dependencies" -type "str"

$user = Get-AnsibleParam -obj $params -name "user" -type "str"
$password = Get-AnsibleParam -obj $params -name "password" -type "str"

if (($appParameters -ne $null) -and ($appParametersFree -ne $null))
{
    Fail-Json $result "Use either app_parameters or app_parameteres_free_form, but not both"
}

#abstract the calling of nssm because some PowerShell environments
#mishandle its stdout(which is Unicode) as UTF8
Function Nssm-Invoke
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$cmd
    )
    Try {
      $encodingWas = [System.Console]::OutputEncoding
      [System.Console]::OutputEncoding = [System.Text.Encoding]::Unicode

      $nssmOutput = invoke-expression "nssm $cmd"
      return $nssmOutput
    }
    Catch {
      $ErrorMessage = $_.Exception.Message
      Fail-Json $result "an exception occurred when invoking NSSM: $ErrorMessage"
    }
    Finally {
      # Set the console encoding back to what it was
      [System.Console]::OutputEncoding = $encodingWas
    }
}

Function Service-Exists
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    return [bool](Get-Service "$name" -ErrorAction SilentlyContinue)
}

Function Nssm-Remove
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    if (Service-Exists -name $name)
    {
        if ((Get-Service -Name $name).Status -ne "Stopped") {
            $cmd = "stop ""$name"""
            $results = Nssm-Invoke $cmd
        }
        $cmd = "remove ""$name"" confirm"
        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error removing service ""$name"""
        }

        $result.changed_by = "remove_service"
        $result.changed = $true
     }
}

Function Nssm-Install
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [Parameter(Mandatory=$true)]
        [AllowEmptyString()]
        [string]$application
    )

    if (!$application)
    {
        Throw "Error installing service ""$name"". No application was supplied."
    }
    If (-Not (Test-Path -Path $application -PathType Leaf)) {
        Throw "$application does not exist on the host"
    }

    if (!(Service-Exists -name $name))
    {
        $results = Nssm-Invoke "install ""$name"" ""$application"""

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error installing service ""$name"""
        }

        $result.changed_by = "install_service"
        $result.changed = $true

     } else {
        $results = Nssm-Invoke "get ""$name"" Application"

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error installing service ""$name"""
        }

        if ($results -cnotlike $application)
        {
            $cmd = "set ""$name"" Application ""$application"""

            $results = Nssm-Invoke $cmd

            if ($LastExitCode -ne 0)
            {
                $result.nssm_error_cmd = $cmd
                $result.nssm_error_log = "$results"
                Throw "Error installing service ""$name"""
            }
            $result.application = "$application"

            $result.changed_by = "reinstall_service"
            $result.changed = $true
        }
     }

     if ($result.changed)
     {
        $applicationPath = (Get-Item $application).DirectoryName
        $cmd = "nssm set ""$name"" AppDirectory ""$applicationPath"""

        $results = invoke-expression $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error installing service ""$name"""
        }
     }
}

Function ParseAppParameters()
{
   [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [AllowEmptyString()]
        [string]$appParameters
    )

    $escapedAppParameters = $appParameters.TrimStart("@").TrimStart("{").TrimEnd("}").Replace("; ","`n").Replace("\","\\")

    return ConvertFrom-StringData -StringData $escapedAppParameters
}


Function Nssm-Update-AppParameters
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [Parameter(Mandatory=$true)]
        [AllowEmptyString()]
        [string]$appParameters,
        [string]$appParametersFree
    )

    $cmd = "get ""$name"" AppParameters"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error updating AppParameters for service ""$name"""
    }

    $appParamKeys = @()
    $appParamVals = @()
    $singleLineParams = ""

    if ($appParameters)
    {
        $appParametersHash = ParseAppParameters -appParameters $appParameters
        $appParametersHash.GetEnumerator() |
            % {
                $key = $($_.Name)
                $val = $($_.Value)

                $appParamKeys += $key
                $appParamVals += $val

                if ($key -eq "_") {
                    $singleLineParams = "$val " + $singleLineParams
                } else {
                    $singleLineParams = $singleLineParams + "$key ""$val"""
                }
            }

        $result.nssm_app_parameters_parsed = $appParametersHash
        $result.nssm_app_parameters_keys = $appParamKeys
        $result.nssm_app_parameters_vals = $appParamVals
    }
    elseif ($appParametersFree) {
        $result.nssm_app_parameters_free_form = $appParametersFree
        $singleLineParams = $appParametersFree
    }

    $result.nssm_app_parameters = $appParameters
    $result.nssm_single_line_app_parameters = $singleLineParams

    if ($results -ne $singleLineParams)
    {
        if ($appParameters -or $appParametersFree)
        {
            $cmd = "set ""$name"" AppParameters $singleLineParams"
        } else {
            $cmd = "set ""$name"" AppParameters '""""'"
        }
        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error updating AppParameters for service ""$name"""
        }

        $result.changed_by = "update_app_parameters"
        $result.changed = $true
    }
}

Function Nssm-Set-Output-Files
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [string]$stdout,
        [string]$stderr
    )

    $cmd = "get ""$name"" AppStdout"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error retrieving existing stdout file for service ""$name"""
    }

    if ($results -cnotlike $stdout)
    {
        if (!$stdout)
        {
            $cmd = "reset ""$name"" AppStdout"
        } else {
            $cmd = "set ""$name"" AppStdout $stdout"
        }

        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error setting stdout file for service ""$name"""
        }

        $result.changed_by = "set_stdout"
        $result.changed = $true
    }

    $cmd = "get ""$name"" AppStderr"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error retrieving existing stderr file for service ""$name"""
    }

    if ($results -cnotlike $stderr)
    {
        if (!$stderr)
        {
            $cmd = "reset ""$name"" AppStderr"
            $results = Nssm-Invoke $cmd

            if ($LastExitCode -ne 0)
            {
                $result.nssm_error_cmd = $cmd
                $result.nssm_error_log = "$results"
                Throw "Error clearing stderr file setting for service ""$name"""
            }
        } else {
            $cmd = "set ""$name"" AppStderr $stderr"
            $results = Nssm-Invoke $cmd

            if ($LastExitCode -ne 0)
            {
                $result.nssm_error_cmd = $cmd
                $result.nssm_error_log = "$results"
                Throw "Error setting stderr file for service ""$name"""
            }
        }

        $result.changed_by = "set_stderr"
        $result.changed = $true
    }

    ###
    # Setup file rotation so we don't accidentally consume too much disk
    ###

    #set files to overwrite
    $cmd = "set ""$name"" AppStdoutCreationDisposition 2"
    $results = Nssm-Invoke $cmd

    $cmd = "set ""$name"" AppStderrCreationDisposition 2"
    $results = Nssm-Invoke $cmd

    #enable file rotation
    $cmd = "set ""$name"" AppRotateFiles 1"
    $results = Nssm-Invoke $cmd

    #don't rotate until the service restarts
    $cmd = "set ""$name"" AppRotateOnline 0"
    $results = Nssm-Invoke $cmd

    #both of the below conditions must be met before rotation will happen
    #minimum age before rotating
    $cmd = "set ""$name"" AppRotateSeconds 86400"
    $results = Nssm-Invoke $cmd

    #minimum size before rotating
    $cmd = "set ""$name"" AppRotateBytes 104858"
    $results = Nssm-Invoke $cmd
}

Function Nssm-Update-Credentials
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [Parameter(Mandatory=$false)]
        [string]$user,
        [Parameter(Mandatory=$false)]
        [string]$password
    )

    $cmd = "get ""$name"" ObjectName"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error updating credentials for service ""$name"""
    }

    if ($user) {
        if (!$password) {
            Throw "User without password is informed for service ""$name"""
        }
        else {
            $fullUser = $user
            If (-Not($user.contains("@")) -And ($user.Split("\").count -eq 1)) {
                $fullUser = ".\" + $user
            }

            If ($results -ne $fullUser) {
                $cmd = "set ""$name"" ObjectName $fullUser '$password'"
                $results = Nssm-Invoke $cmd

                if ($LastExitCode -ne 0)
                {
                    $result.nssm_error_cmd = $cmd
                    $result.nssm_error_log = "$results"
                    Throw "Error updating credentials for service ""$name"""
                }

                $result.changed_by = "update_credentials"
                $result.changed = $true
            }
        }
    }
}

Function Nssm-Update-Dependencies
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [Parameter(Mandatory=$false)]
        [string]$dependencies
    )

    $cmd = "get ""$name"" DependOnService"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error updating dependencies for service ""$name"""
    }

    If (($dependencies) -and ($results.Tolower() -ne $dependencies.Tolower())) {
        $cmd = "set ""$name"" DependOnService $dependencies"
        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error updating dependencies for service ""$name"""
        }

        $result.changed_by = "update-dependencies"
        $result.changed = $true
    }
}

Function Nssm-Update-StartMode
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name,
        [Parameter(Mandatory=$true)]
        [string]$mode
    )

    $cmd = "get ""$name"" Start"
    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error updating start mode for service ""$name"""
    }

    $modes=@{"auto" = "SERVICE_AUTO_START"; "manual" = "SERVICE_DEMAND_START"; "disabled" = "SERVICE_DISABLED"}
    $mappedMode = $modes.$mode
    if ($results -cnotlike $mappedMode) {
        $cmd = "set ""$name"" Start $mappedMode"
        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error updating start mode for service ""$name"""
        }

        $result.changed_by = "start_mode"
        $result.changed = $true
    }
}

Function Nssm-Get-Status
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    $cmd = "status ""$name"""
    $results = Nssm-Invoke $cmd

    return ,$results
}

Function Nssm-Start
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    $currentStatus = Nssm-Get-Status -name $name

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error starting service ""$name"""
    }

    switch ($currentStatus)
    {
        "SERVICE_RUNNING" { <# Nothing to do #> }
        "SERVICE_STOPPED" { Nssm-Start-Service-Command -name $name }

        "SERVICE_CONTINUE_PENDING" { Nssm-Stop-Service-Command -name $name; Nssm-Start-Service-Command -name $name }
        "SERVICE_PAUSE_PENDING" { Nssm-Stop-Service-Command -name $name; Nssm-Start-Service-Command -name $name }
        "SERVICE_PAUSED" { Nssm-Stop-Service-Command -name $name; Nssm-Start-Service-Command -name $name }
        "SERVICE_START_PENDING" { Nssm-Stop-Service-Command -name $name; Nssm-Start-Service-Command -name $name }
        "SERVICE_STOP_PENDING" { Nssm-Stop-Service-Command -name $name; Nssm-Start-Service-Command -name $name }
    }
}

Function Nssm-Start-Service-Command
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    $cmd = "start ""$name"""

    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error starting service ""$name"""
    }

    $result.changed_by = "start_service"
    $result.changed = $true
}

Function Nssm-Stop-Service-Command
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    $cmd = "stop ""$name"""

    $results = Nssm-Invoke $cmd

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error stopping service ""$name"""
    }

    $result.changed_by = "stop_service_command"
    $result.changed = $true
}

Function Nssm-Stop
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    $currentStatus = Nssm-Get-Status -name $name

    if ($LastExitCode -ne 0)
    {
        $result.nssm_error_cmd = $cmd
        $result.nssm_error_log = "$results"
        Throw "Error stopping service ""$name"""
    }

    if ($currentStatus -ne "SERVICE_STOPPED")
    {
        $cmd = "stop ""$name"""

        $results = Nssm-Invoke $cmd

        if ($LastExitCode -ne 0)
        {
            $result.nssm_error_cmd = $cmd
            $result.nssm_error_log = "$results"
            Throw "Error stopping service ""$name"""
        }

        $result.changed_by = "stop_service"
        $result.changed = $true
    }
}

Function Nssm-Restart
{
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$name
    )

    Nssm-Stop-Service-Command -name $name
    Nssm-Start-Service-Command -name $name
}

Function NssmProcedure
{
    Nssm-Install -name $name -application $application
    Nssm-Update-AppParameters -name $name -appParameters $appParameters -appParametersFree $appParametersFree
    Nssm-Set-Output-Files -name $name -stdout $stdoutFile -stderr $stderrFile
    Nssm-Update-Dependencies -name $name -dependencies $dependencies
    Nssm-Update-Credentials -name $name -user $user -password $password
    Nssm-Update-StartMode -name $name -mode $startMode
}

Try
{
    switch ($state)
    {
        "absent" {
            Nssm-Remove -name $name
        }
        "present" {
            NssmProcedure
        }
        "started" {
            NssmProcedure
            Nssm-Start -name $name
        }
        "stopped" {
            NssmProcedure
            Nssm-Stop -name $name
        }
        "restarted" {
            NssmProcedure
            Nssm-Restart -name $name
        }
    }

    Exit-Json $result
}
Catch
{
     Fail-Json $result $_.Exception.Message
}
