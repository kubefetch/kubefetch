#!powershell
# This file is part of Ansible
#
# (c) 2017, Jordan Borean <jborean93@gmail.com>, and others
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

$ErrorActionPreference = "Stop"

$params = Parse-Args -arguments $args -supports_check_mode $true
$check_mode = Get-AnsibleParam -obj $params -name "_ansible_check_mode" -type "bool" -default $false
$diff_mode = Get-AnsibleParam -obj $Params -name "_ansible_diff" -type "bool" -default $false

$name = Get-AnsibleParam -obj $params -name "name" -type "str" -failifempty $true
$display_name = Get-AnsibleParam -obj $params -name "display_name" -type "str"
$domain_username = Get-AnsibleParam -obj $params -name "domain_username" -type "str"
$domain_password = Get-AnsibleParam -obj $params -name "domain_password" -type "str" -failifempty ($domain_username -ne $null)
$description = Get-AnsibleParam -obj $params -name "description" -type "str"
$category = Get-AnsibleParam -obj $params -name "category" -type "str" -validateset "distribution","security"
$scope = Get-AnsibleParam -obj $params -name "scope" -type "str" -validateset "domainlocal","global","universal"
$managed_by = Get-AnsibleParam -obj $params -name "managed_by" -type "str"
$attributes = Get-AnsibleParam -obj $params -name "attributes"
$organizational_unit = Get-AnsibleParam -obj $params -name "organizational_unit" -type "str" -aliases "ou","path"
$state = Get-AnsibleParam -obj $params -name "state" -type "str" -default "present" -validateset "present","absent"
$protect = Get-AnsibleParam -obj $params -name "protect" -type "bool"
$ignore_protection = Get-AnsibleParam -obj $params -name "ignore_protection" -type "bool" -default $false

$result = @{
    changed = $false
}

if ($diff_mode) {
    $result.diff = @{}
}

if (-not (Get-Module -Name ActiveDirectory -ListAvailable)) {
    Fail-Json $result "win_domain_group requires the ActiveDirectory PS module to be installed"
}
Import-Module ActiveDirectory

$extra_args = @{}
if ($domain_username -ne $null) {
    $domain_password = ConvertTo-SecureString $domain_password -AsPlainText -Force
    $credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $domain_username, $domain_password
    $extra_args.Credential = $credential
}

try {
    $group = Get-ADGroup -Identity $name -Properties * @extra_args
} catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
    $group = $null
} catch {
    Fail-Json $result "failed to retrieve initial details for group $($name): $($_.Exception.Message)"
}
if ($state -eq "absent") {
    if ($group -ne $null) {
        if ($group.ProtectedFromAccidentalDeletion -eq $true -and $ignore_protection -eq $true) {
            $group = $group | Set-ADObject -ProtectedFromAccidentalDeletion $false -WhatIf:$check_mode -PassThru @extra_args
        } elseif ($group.ProtectedFromAccidentalDeletion -eq $true -and $ignore_protection -eq $false) {
            Fail-Json $result "cannot delete group $name when ProtectedFromAccidentalDeletion is turned on, run this module with ignore_protection=true to override this"
        }

        try {
            $group | Remove-ADGroup -Confirm:$false -WhatIf:$check_mode @extra_args
        } catch {
            Fail-Json $result "failed to remove group $($name): $($_.Exception.Message)"
        }
        
        $result.changed = $true
        if ($diff_mode) {
            $result.diff.prepared = "-[$name]"
        }
    }
} else {
    # validate that path is an actual path
    if ($organizational_unit -ne $null) {
        try {
            Get-ADObject -Identity $organizational_unit @extra_args | Out-Null
        } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
            Fail-Json $result "the group path $organizational_unit does not exist, please specify a valid LDAP path"
        }
    }

    $diff_text = $null
    if ($group -ne $null) {
        # will be overriden later if no change actually occurs
        $diff_text += "[$name]`n"

        # change the path of the group
        if ($organizational_unit -ne $null) {
            $group_cn = $group.CN
            $existing_path = $group.DistinguishedName -replace "^CN=$group_cn,",''
            if ($existing_path -ne $organizational_unit) {
                $protection_disabled = $false
                if ($group.ProtectedFromAccidentalDeletion -eq $true -and $ignore_protection -eq $true) {
                    $group | Set-ADObject -ProtectedFromAccidentalDeletion $false -WhatIf:$check_mode -PassThru @extra_args | Out-Null
                    $protection_disabled = $true
                } elseif ($group.ProtectedFromAccidentalDeletion -eq $true -and $ignore_protection -eq $false) {
                    Fail-Json $result "cannot move group $name when ProtectedFromAccidentalDeletion is turned on, run this module with ignore_protection=true to override this"
                }

                try {
                    $group = $group | Move-ADObject -Targetpath $organizational_unit -WhatIf:$check_mode -PassThru @extra_args
                } catch {
                    Fail-Json $result "failed to move group from $existing_path to $($organizational_unit): $($_.Exception.Message)"
                } finally {
                    if ($protection_disabled -eq $true) {
                        $group | Set-ADObject -ProtectedFromAccidentalDeletion $true -WhatIf:$check_mode -PassThru @extra_args | Out-Null
                    }
                }
                
                $result.changed = $true
                $diff_text += "-DistinguishedName = CN=$group_cn,$existing_path`n+DistinguishedName = CN=$group_cn,$organizational_unit`n"

                if ($protection_disabled -eq $true) {
                    $group | Set-ADObject -ProtectedFromAccidentalDeletion $true -WhatIf:$check_mode @extra_args | Out-Null
                }
                # get the group again once we have moved it
                $group = Get-ADGroup -Identity $name -Properties * @extra_args
            }
        }

        # change attributes of group
        $extra_scope_change = $null
        $run_change = $false
        $set_args = $extra_args.Clone()

        if ($scope -ne $null) {
            if ($group.GroupScope -ne $scope) {
                # you cannot from from Global to DomainLocal and vice-versa, we
                # need to change it to Universal and then finally to the target
                # scope
                if ($group.GroupScope -eq "global" -and $scope -eq "domainlocal") {
                    $set_args.GroupScope = "Universal"
                    $extra_scope_change = $scope
                } elseif ($group.GroupScope -eq "domainlocal" -and $scope -eq "global") {
                    $set_args.GroupScope = "Universal"
                    $extra_scope_change = $scope
                } else {
                    $set_args.GroupScope = $scope
                }
                $run_change = $true
                $diff_text += "-GroupScope = $($group.GroupScope)`n+GroupScope = $scope`n"
            }
        }

        if ($description -ne $null -and $group.Description -cne $description) {
            $set_args.Description = $description
            $run_change = $true
            $diff_text += "-Description = $($group.Description)`n+Description = $description`n"
        }

        if ($display_name -ne $null -and $group.DisplayName -cne $display_name) {
            $set_args.DisplayName = $display_name
            $run_change = $true
            $diff_text += "-DisplayName = $($group.DisplayName)`n+DisplayName = $display_name`n"
        }

        if ($category -ne $null -and $group.GroupCategory -ne $category) {
            $set_args.GroupCategory = $category
            $run_change = $true
            $diff_text += "-GroupCategory = $($group.GroupCategory)`n+GroupCategory = $category`n"
        }

        if ($managed_by -ne $null) {
            if ($group.ManagedBy -eq $null) {
                $set_args.ManagedBy = $managed_by
                $run_change = $true
                $diff_text += "+ManagedBy = $managed_by`n"
            } else {
                try {
                    $managed_by_object = Get-ADGroup -Identity $managed_by @extra_args
                } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
                    try {
                        $managed_by_object = Get-ADUser -Identity $managed_by @extra_args
                    } catch [Microsoft.ActiveDirectory.Management.ADIdentityNotFoundException] {
                        Fail-Json $result "failed to find managed_by user or group $managed_by to be used for comparison"
                    }
                }

                if ($group.ManagedBy -ne $managed_by_object.DistinguishedName) {
                    $set_args.ManagedBy = $managed_by
                    $run_change = $true
                    $diff_text += "-ManagedBy = $($group.ManagedBy)`n+ManagedBy = $($managed_by_object.DistinguishedName)`n"
                }
            }
        }

        if ($attributes -ne $null) {
            $add_attributes = @{}
            $replace_attributes = @{}
            foreach ($attribute in $attributes.GetEnumerator()) {
                $attribute_name = $attribute.Name
                $attribute_value = $attribute.Value

                $valid_property = [bool]($group.PSobject.Properties.name -eq $attribute_name)
                if ($valid_property) {
                    $existing_value = $group.$attribute_name
                    if ($existing_value -cne $attribute_value) {
                        $replace_attributes.$attribute_name = $attribute_value
                        $diff_text += "-$attribute_name = $existing_value`n+$attribute_name = $attribute_value`n"
                    }                
                } else {
                    $add_attributes.$attribute_name = $attribute_value
                    $diff_text += "+$attribute_name = $attribute_value`n"
                }
            }
            if ($add_attributes.Count -gt 0) {
                $set_args.Add = $add_attributes
                $run_change = $true
            }
            if ($replace_attributes.Count -gt 0) {
                $set_args.Replace = $replace_attributes
                $run_change = $true
            }
        }

        if ($run_change) {
            try {
                $group = $group | Set-ADGroup -WhatIf:$check_mode -PassThru @set_args
            } catch {
                Fail-Json $result "failed to change group $($name): $($_.Exception.Message)"
            }
            $result.changed = $true

            if ($extra_scope_change -ne $null) {
                try {
                    $group = $group | Set-ADGroup -GroupScope $extra_scope_change -WhatIf:$check_mode -PassThru @extra_args
                } catch {
                    Fail-Json $result "failed to change scope of group $name to $($scope): $($_.Exception.Message)"
                }
            }
        }

        # make sure our diff text is null if no change occured
        if ($result.changed -eq $false) {
            $diff_text = $null
        }
    } else {
        # validate if scope is set
        if ($scope -eq $null) {
            Fail-Json $result "scope must be set when state=present and the group doesn't exist"
        }

        $diff_text += "+[$name]`n+Scope = $scope`n"
        $add_args = $extra_args.Clone()
        $add_args.Name = $name
        $add_args.GroupScope = $scope

        if ($description -ne $null) {
            $add_args.Description = $description
            $diff_text += "+Description = $description`n"
        }

        if ($display_name -ne $null) {
            $add_args.DisplayName = $display_name
            $diff_text += "+DisplayName = $display_name`n"
        }

        if ($category -ne $null) {
            $add_args.GroupCategory = $category
            $diff_text += "+GroupCategory = $category`n"
        }

        if ($managed_by -ne $null) {
            $add_args.ManagedBy = $managed_by
            $diff_text += "+ManagedBy = $managed_by`n"
        }

        if ($attributes -ne $null) {
            $add_args.OtherAttributes = $attributes
            foreach ($attribute in $attributes.GetEnumerator()) {
                $diff_text += "+$($attribute.Name) = $($attribute.Value)`n"
            }
        }

        if ($organizational_unit -ne $null) {
            $add_args.Path = $organizational_unit
            $diff_text += "+Path = $organizational_unit`n"
        }

        try {
            $group = New-AdGroup -WhatIf:$check_mode -PassThru @add_args
        } catch {
            Fail-Json $result "failed to create group $($name): $($_.Exception.Message)"
        }
        $result.changed = $true
    }

    # set the protection value
    if ($protect -ne $null) {
        if (-not $check_mode) {
            $group = Get-ADGroup -Identity $name -Properties * @extra_args
        }
        $existing_protection_value = $group.ProtectedFromAccidentalDeletion
        if ($existing_protection_value -eq $null) {
            $existing_protection_value = $false
        }
        if ($existing_protection_value -ne $protect) {
            $diff_text += @"
-ProtectedFromAccidentalDeletion = $existing_protection_value
+ProtectedFromAccidentalDeletion = $protect
"@

            $group | Set-ADObject -ProtectedFromAccidentalDeletion $protect -WhatIf:$check_mode -PassThru @extra_args
            $result.changed = $true
        }
    }

    if ($diff_mode -and $diff_text -ne $null) {
        $result.diff.prepared = $diff_text
    }

    if (-not $check_mode) {
        $group = Get-ADGroup -Identity $name -Properties * @extra_args
        $result.sid = $group.SID.Value
        $result.description = $group.Description
        $result.distinguished_name = $group.DistinguishedName
        $result.display_name = $group.DisplayName
        $result.name = $group.Name
        $result.canonical_name = $group.CanonicalName
        $result.guid = $group.ObjectGUID
        $result.protected_from_accidental_deletion = $group.ProtectedFromAccidentalDeletion
        $result.managed_by = $group.ManagedBy
        $result.group_scope = ($group.GroupScope).ToString()
        $result.category = ($group.GroupCategory).ToString()

        if ($attributes -ne $null) {
            $result.attributes = @{}
            foreach ($attribute in $attributes.GetEnumerator()) {
                $attribute_name = $attribute.Name
                $result.attributes.$attribute_name = $group.$attribute_name
            }
        }
    }
}

Exit-Json $result
