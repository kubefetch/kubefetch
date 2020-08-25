#!powershell
# Copyright 2015, Hans-Joachim Kliemeck <git@kliemeck.de>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

#Requires -Module Ansible.ModuleUtils.Legacy.psm1
#Requires -Module Ansible.ModuleUtils.SID.psm1

$result = @{
    changed = $false
}

$params = Parse-Args $args -supports_check_mode $true
$check_mode = Get-AnsibleParam -obj $params -name "_ansible_check_mode" -type "bool" -default $false

$path = Get-AnsibleParam -obj $params -name "path" -type "path" -failifempty $true
$user = Get-AnsibleParam -obj $params -name "user" -type "str" -failifempty $true
$recurse = Get-AnsibleParam -obj $params -name "recurse" -type "bool" -default $false -resultobj $result

If (-Not (Test-Path -Path $path)) {
    Fail-Json $result "$path file or directory does not exist on the host"
}

# Test that the user/group is resolvable on the local machine
$sid = Convert-ToSID -account_name $user
if (!$sid) {
    Fail-Json $result "$user is not a valid user or group on the host machine or domain"
}

Try {
    $objUser = New-Object System.Security.Principal.SecurityIdentifier($sid)

    $file = Get-Item -Path $path
    $acl = Get-Acl $file.FullName

    If ($acl.getOwner([System.Security.Principal.SecurityIdentifier]) -ne $objUser) {
        $acl.setOwner($objUser)
        Set-Acl -Path $file.FullName -AclObject $acl -WhatIf:$check_mode
        $result.changed = $true
    }

    If ($recurse) {
        $files = Get-ChildItem -Path $path -Force -Recurse
        ForEach($file in $files){
            $acl = Get-Acl $file.FullName

            If ($acl.getOwner([System.Security.Principal.SecurityIdentifier]) -ne $objUser) {
                $acl.setOwner($objUser)
                Set-Acl -Path $file.FullName -AclObject $acl -WhatIf:$check_mode
                $result.changed = $true
            }
        }
    }
}
Catch {
    Fail-Json $result "an error occurred when attempting to change owner on $path for $($user): $($_.Exception.Message)"
}

Exit-Json $result
