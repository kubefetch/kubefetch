#!powershell
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

# FUTURE: consider action wrapper to manage reboots and credential changes

Function Ensure-Prereqs {
    $gwf = Get-WindowsFeature AD-Domain-Services
    If($gwf.InstallState -ne "Installed") {
        $result.changed = $true

        If($check_mode) {
            Exit-Json $result
        }
        $awf = Add-WindowsFeature AD-Domain-Services
        # FUTURE: check if reboot necessary
    }
}

$parsed_args = Parse-Args $args -supports_check_mode $true
$check_mode = Get-AnsibleParam $parsed_args "_ansible_check_mode" -default $false
$dns_domain_name = Get-AnsibleParam $parsed_args "dns_domain_name" -failifempty $true
$safe_mode_admin_password = Get-AnsibleParam $parsed_args "safe_mode_password" -failifempty $true

$forest = $null

# FUTURE: support down to Server 2012?
If([System.Environment]::OSVersion.Version -lt [Version]"6.3.9600.0") {
    Fail-Json -message "win_domain requires Windows Server 2012R2 or higher"
}

$result = @{changed=$false; reboot_required=$false}

# FUTURE: any sane way to do the detection under check-mode *without* installing the feature?

Ensure-Prereqs

Try {
    $forest = Get-ADForest $dns_domain_name -ErrorAction SilentlyContinue
}
Catch { }

If(-not $forest) {
    $result.changed = $true

    If(-not $check_mode) {
        $sm_cred = ConvertTo-SecureString $safe_mode_admin_password -AsPlainText -Force

        $install_forest_args = @{
            DomainName=$dns_domain_name;
            SafeModeAdministratorPassword=$sm_cred;
            Confirm=$false;
            SkipPreChecks=$true;
            InstallDNS=$true;
            NoRebootOnCompletion=$true;
        }

        $iaf = Install-ADDSForest @install_forest_args

        $result.reboot_required = $iaf.RebootRequired
    }
}

Exit-Json $result
