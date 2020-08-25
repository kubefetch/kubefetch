#!powershell

# (c) 2017, Red Hat, Inc.
#
# This file is part of Ansible
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

# WANT_JSON
# POWERSHELL_COMMON

Set-StrictMode -Version 2

$ErrorActionPreference = "Stop"
$ConfirmPreference = "None"

$log_path = $null

Function Write-DebugLog {
    Param(
        [string]$msg
    )

    $DebugPreference = "Continue"
    $ErrorActionPreference = "Continue"
    $date_str = Get-Date -Format u
    $msg = "$date_str $msg"

    Write-Debug $msg

    if($log_path) {
        Add-Content $log_path $msg
    }
}

$required_features = @("AD-Domain-Services","RSAT-ADDS")

Function Get-MissingFeatures {
    Write-DebugLog "Checking for missing Windows features..."

    $features = @(Get-WindowsFeature $required_features)

    If($features.Count -ne $required_features.Count) {
        Throw "One or more Windows features required for a domain controller are unavailable"
    }

    $missing_features = @($features | Where-Object InstallState -ne Installed)
    
    return ,$missing_features # no, the comma's not a typo- allows us to return an empty array
}

Function Ensure-FeatureInstallation {
    # ensure RSAT-ADDS and AD-Domain-Services features are installed

    Write-DebugLog "Ensuring required Windows features are installed..." 
    $feature_result = Install-WindowsFeature $required_features

    If(-not $feature_result.Success) {
        Exit-Json -message ("Error installing AD-Domain-Services and RSAT-ADDS features: {0}" -f ($feature_result | Out-String))
    }
}

# return the domain we're a DC for, or null if not a DC
Function Get-DomainControllerDomain {
    Write-DebugLog "Checking for domain controller role and domain name"

    $sys_cim = Get-WmiObject Win32_ComputerSystem

    $is_dc = $sys_cim.DomainRole -in (4,5) # backup/primary DC
    # this will be our workgroup or joined-domain if we're not a DC
    $domain = $sys_cim.Domain

    Switch($is_dc) {
        $true { return $domain }
        Default { return $null }
    }
}

Function Create-Credential {
    Param(
        [string] $cred_user,
        [string] $cred_password
    )

    $cred = New-Object System.Management.Automation.PSCredential($cred_user, $($cred_password | ConvertTo-SecureString -AsPlainText -Force))

    Return $cred
}

Function Get-OperationMasterRoles {
    $assigned_roles = @((Get-ADDomainController -Server localhost).OperationMasterRoles)

    Return ,$assigned_roles # no, the comma's not a typo- allows us to return an empty array
}

$result = @{
    changed = $false
    reboot_required = $false
}

$param = Parse-Args -arguments $args -supports_check_mode $true

$dns_domain_name = Get-AnsibleParam $param "dns_domain_name"
$safe_mode_password= Get-AnsibleParam $param "safe_mode_password"
$domain_admin_user = Get-AnsibleParam $param "domain_admin_user" -failifempty $result
$domain_admin_password= Get-AnsibleParam $param "domain_admin_password" -failifempty $result
$local_admin_password= Get-AnsibleParam $param "local_admin_password"

$state = Get-AnsibleParam $param "state" -validateset ("domain_controller", "member_server") -failifempty $result
$log_path = Get-AnsibleParam $param "log_path"
$_ansible_check_mode = Get-AnsibleParam $param "_ansible_check_mode" -default $false

$global:log_path = $log_path

Try {
    # ensure target OS support; < 2012 doesn't have cmdlet support for DC promotion
    If(-not (Get-Command Install-WindowsFeature -ErrorAction SilentlyContinue)) {
        Fail-Json -message "win_domain_controller requires at least Windows Server 2012"
    }

    # validate args
    If($state -eq "domain_controller") {
        If(-not $dns_domain_name) {
            Fail-Json -message "dns_domain_name is required when desired state is 'domain_controller'"
        }

        If(-not $safe_mode_password) {
            Fail-Json -message "safe_mode_password is required when desired state is 'domain_controller'"
        }

        # ensure that domain admin user is in UPN or down-level domain format (prevent hang from https://support.microsoft.com/en-us/kb/2737935)
        If(-not $domain_admin_user.Contains("\") -and -not $domain_admin_user.Contains("@")) {
            Fail-Json -message "domain_admin_user must be in domain\user or user@domain.com format"
        }
    }
    Else { # member_server
        If(-not $local_admin_password) {
            Fail-Json -message "local_admin_password is required when desired state is 'member_server'"
        }
    }

    # short-circuit "member server" check, since we don't need feature checks for this...

    $current_dc_domain = Get-DomainControllerDomain

    If($state -eq "member_server" -and -not $current_dc_domain) {
        Exit-Json $result
    }

    # all other operations will require the AD-DS and RSAT-ADDS features...

    $missing_features = Get-MissingFeatures

    If($missing_features.Count -gt 0) {
        Write-DebugLog ("Missing Windows features ({0}), need to install" -f ($missing_features -join ", "))
        $result.changed = $true # we need to install features
        If($_ansible_check_mode) {
            # bail out here- we can't proceed without knowing the features are installed
            Write-DebugLog "check-mode, exiting early"
            Exit-Json $result
        }

        Ensure-FeatureInstallation | Out-Null
    }

    $domain_admin_cred = Create-Credential -cred_user $domain_admin_user -cred_password $domain_admin_password

    switch($state) {
        domain_controller {
            If(-not $safe_mode_password) {
                Fail-Json -message "safe_mode_password is required for state=domain_controller"
            }

            If($current_dc_domain) {
                # FUTURE: implement managed Remove/Add to change domains?

                If($current_dc_domain -ne $dns_domain_name) {
                    Fail-Json "$(hostname) is a domain controller for domain $current_dc_domain; changing DC domains is not implemented"
                }
            }

            # need to promote to DC
            If(-not $current_dc_domain) {
                Write-DebugLog "Not currently a domain controller; needs promotion"
                $result.changed = $true
                If($_ansible_check_mode) {
                    Write-DebugLog "check-mode, exiting early"
                    Fail-Json -message $result
                }

                $result.reboot_required = $true

                $safe_mode_secure = $safe_mode_password | ConvertTo-SecureString -AsPlainText -Force
                Write-DebugLog "Installing domain controller..."

                $install_result = Install-ADDSDomainController -NoRebootOnCompletion -DomainName $dns_domain_name -Credential $domain_admin_cred -SafeModeAdministratorPassword $safe_mode_secure -Force

                Write-DebugLog "Installation completed, needs reboot..."
            }
        }
        member_server {
            If(-not $local_admin_password) {
                Fail-Json -message "local_admin_password is required for state=domain_controller"
            }
            # at this point we already know we're a DC and shouldn't be...
            Write-DebugLog "Need to uninstall domain controller..."
            $result.changed = $true

            Write-DebugLog "Checking for operation master roles assigned to this DC..."

            $assigned_roles = Get-OperationMasterRoles

            # FUTURE: figure out a sane way to hand off roles automatically (designated recipient server, randomly look one up?)
            If($assigned_roles.Count -gt 0) {
                Fail-Json -message ("This domain controller has operation master role(s) ({0}) assigned; they must be moved to other DCs before demotion (see Move-ADDirectoryServerOperationMasterRole)" -f ($assigned_roles -join ", "))
            }

            If($_ansible_check_mode) {
                Write-DebugLog "check-mode, exiting early"
                Exit-Json $result
            }

            $result.reboot_required = $true

            $local_admin_secure = $local_admin_password | ConvertTo-SecureString -AsPlainText -Force

            Write-DebugLog "Uninstalling domain controller..."
            $uninstall_result = Uninstall-ADDSDomainController -NoRebootOnCompletion -LocalAdministratorPassword $local_admin_secure -Credential $domain_admin_cred
            Write-DebugLog "Uninstallation complete, needs reboot..."
        }
        default { throw ("invalid state {0}" -f $state) }
    }

    Exit-Json $result
}
Catch {
    $excep = $_

    Write-DebugLog "Exception: $($excep | out-string)"

    Throw
}


