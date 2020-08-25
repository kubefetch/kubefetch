#!/usr/bin/env bash

set -eux

MYTMPDIR=$(mktemp -d 2>/dev/null || mktemp -d -t 'mytmpdir')
trap 'rm -rf "${MYTMPDIR}"' EXIT

# create a test file
TEST_FILE="${MYTMPDIR}/test_file"
echo "This is a test file" > "${TEST_FILE}"

TEST_FILE_1_2="${MYTMPDIR}/test_file_1_2"
echo "This is a test file for format 1.2" > "${TEST_FILE_1_2}"

TEST_FILE_OUTPUT="${MYTMPDIR}/test_file_output"

TEST_FILE_EDIT="${MYTMPDIR}/test_file_edit"
echo "This is a test file for edit" > "${TEST_FILE_EDIT}"

TEST_FILE_EDIT2="${MYTMPDIR}/test_file_edit2"
echo "This is a test file for edit2" > "${TEST_FILE_EDIT2}"

FORMAT_1_1_HEADER="\$ANSIBLE_VAULT;1.1;AES256"
FORMAT_1_2_HEADER="\$ANSIBLE_VAULT;1.2;AES256"


VAULT_PASSWORD_FILE=vault-password

# Use linux setsid to test without a tty. No setsid if osx/bsd though...
if [ -x "$(command -v setsid)" ]; then
    # tests related to https://github.com/ansible/ansible/issues/30993
    CMD='ansible-playbook -vvvvv --ask-vault-pass test_vault.yml'
    setsid sh -c "echo test-vault-password|${CMD}" < /dev/null > log 2>&1 && :
    WRONG_RC=$?
    cat log
    echo "rc was $WRONG_RC (0 is expected)"
    [ $WRONG_RC -eq 0 ]

    setsid sh -c 'tty; ansible-vault --ask-vault-pass -vvvvv view test_vault.yml' < /dev/null > log 2>&1 && :
    WRONG_RC=$?
    echo "rc was $WRONG_RC (1 is expected)"
    [ $WRONG_RC -eq 1 ]
    cat log

    setsid sh -c 'tty; echo passbhkjhword|ansible-playbook -vvvvv --ask-vault-pass test_vault.yml' < /dev/null > log 2>&1 && :
    WRONG_RC=$?
    echo "rc was $WRONG_RC (1 is expected)"
    [ $WRONG_RC -eq 1 ]
    cat log

    setsid sh -c 'tty; echo test-vault-password |ansible-playbook -vvvvv --ask-vault-pass test_vault.yml' < /dev/null > log 2>&1
    echo $?
    cat log

    setsid sh -c 'tty; echo test-vault-password|ansible-playbook -vvvvv --ask-vault-pass test_vault.yml' < /dev/null > log 2>&1
    echo $?
    cat log

    setsid sh -c 'tty; echo test-vault-password |ansible-playbook -vvvvv --ask-vault-pass test_vault.yml' < /dev/null > log 2>&1
    echo $?
    cat log

    setsid sh -c 'tty; echo test-vault-password|ansible-vault --ask-vault-pass -vvvvv view vaulted.inventory' < /dev/null > log 2>&1
    echo $?
    cat log
fi

# old format
ansible-vault view "$@" --vault-password-file vault-password-ansible format_1_0_AES.yml

ansible-vault view "$@" --vault-password-file vault-password-ansible format_1_1_AES.yml

# old format, wrong password
echo "The wrong password tests are expected to return 1"
ansible-vault view "$@" --vault-password-file vault-password-wrong format_1_0_AES.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

ansible-vault view "$@" --vault-password-file vault-password-wrong format_1_1_AES.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

ansible-vault view "$@" --vault-password-file vault-password-wrong format_1_1_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

set -eux


# new format, view
ansible-vault view "$@" --vault-password-file vault-password format_1_1_AES256.yml

# new format, view with vault-id
ansible-vault view "$@" --vault-id=vault-password format_1_1_AES256.yml

# new format, view, using password script
ansible-vault view "$@" --vault-password-file password-script.py format_1_1_AES256.yml

# new format, view, using password script with vault-id
ansible-vault view "$@" --vault-id password-script.py format_1_1_AES256.yml

# new 1.2 format, view
ansible-vault view "$@" --vault-password-file vault-password format_1_2_AES256.yml

# new 1.2 format, view with vault-id
ansible-vault view "$@" --vault-id=test_vault_id@vault-password format_1_2_AES256.yml

# new 1,2 format, view, using password script
ansible-vault view "$@" --vault-password-file password-script.py format_1_2_AES256.yml

# new 1.2 format, view, using password script with vault-id
ansible-vault view "$@" --vault-id password-script.py format_1_2_AES256.yml

# newish 1.1 format, view, using a vault-id list from config env var
ANSIBLE_VAULT_IDENTITY_LIST='wrong-password@vault-password-wrong,default@vault-password' ansible-vault view "$@" --vault-id password-script.py format_1_1_AES256.yml

# new 1.2 format, view, ENFORCE_IDENTITY_MATCH=true, should fail, no 'test_vault_id' vault_id
ANSIBLE_VAULT_ID_MATCH=1 ansible-vault view "$@" --vault-password-file vault-password format_1_2_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# new 1.2 format, view with vault-id, ENFORCE_IDENTITY_MATCH=true, should work, 'test_vault_id' is provided
ANSIBLE_VAULT_ID_MATCH=1 ansible-vault view "$@" --vault-id=test_vault_id@vault-password format_1_2_AES256.yml

# new 1,2 format, view, using password script, ENFORCE_IDENTITY_MATCH=true, should fail, no 'test_vault_id'
ANSIBLE_VAULT_ID_MATCH=1 ansible-vault view "$@" --vault-password-file password-script.py format_1_2_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]


# new 1.2 format, view, using password script with vault-id, ENFORCE_IDENTITY_MATCH=true, should fail
ANSIBLE_VAULT_ID_MATCH=1 ansible-vault view "$@" --vault-id password-script.py format_1_2_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# new 1.2 format, view, using password script with vault-id, ENFORCE_IDENTITY_MATCH=true, 'test_vault_id' provided should work
ANSIBLE_VAULT_ID_MATCH=1 ansible-vault view "$@" --vault-id=test_vault_id@password-script.py format_1_2_AES256.yml

# test with a default vault password set via config/env, right password
ANSIBLE_VAULT_PASSWORD_FILE=vault-password ansible-vault view "$@" format_1_1_AES256.yml

# test with a default vault password set via config/env, wrong password
ANSIBLE_VAULT_PASSWORD_FILE=vault-password-wrong ansible-vault view "$@" format_1_1_AES.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# test with a default vault-id list set via config/env, right password
ANSIBLE_VAULT_PASSWORD_FILE=wrong@vault-password-wrong,correct@vault-password ansible-vault view "$@" format_1_1_AES.yml && :

# test with a default vault-id list set via config/env,wrong passwords
ANSIBLE_VAULT_PASSWORD_FILE=wrong@vault-password-wrong,alsowrong@vault-password-wrong ansible-vault view "$@" format_1_1_AES.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# encrypt it
ansible-vault encrypt "$@" --vault-password-file vault-password "${TEST_FILE}"

ansible-vault view "$@" --vault-password-file vault-password "${TEST_FILE}"

# view with multiple vault-password files, including a wrong one
ansible-vault view "$@" --vault-password-file vault-password --vault-password-file vault-password-wrong "${TEST_FILE}"

# view with multiple vault-password files, including a wrong one, using vault-id
ansible-vault view "$@" --vault-id vault-password --vault-id vault-password-wrong "${TEST_FILE}"

# And with the password files specified in a different order
ansible-vault view "$@" --vault-password-file vault-password-wrong --vault-password-file vault-password "${TEST_FILE}"

# And with the password files specified in a different order, using vault-id
ansible-vault view "$@" --vault-id vault-password-wrong --vault-id vault-password "${TEST_FILE}"

# And with the password files specified in a different order, using --vault-id and non default vault_ids
ansible-vault view "$@" --vault-id test_vault_id@vault-password-wrong --vault-id test_vault_id@vault-password "${TEST_FILE}"

ansible-vault decrypt "$@" --vault-password-file vault-password "${TEST_FILE}"

# encrypt it, using a vault_id so we write a 1.2 format file
ansible-vault encrypt "$@" --vault-id test_vault_1_2@vault-password "${TEST_FILE_1_2}"

ansible-vault view "$@" --vault-id vault-password "${TEST_FILE_1_2}"
ansible-vault view "$@" --vault-id test_vault_1_2@vault-password "${TEST_FILE_1_2}"

# view with multiple vault-password files, including a wrong one
ansible-vault view "$@" --vault-id vault-password --vault-id wrong_password@vault-password-wrong "${TEST_FILE_1_2}"

# And with the password files specified in a different order, using vault-id
ansible-vault view "$@" --vault-id vault-password-wrong --vault-id vault-password "${TEST_FILE_1_2}"

# And with the password files specified in a different order, using --vault-id and non default vault_ids
ansible-vault view "$@" --vault-id test_vault_id@vault-password-wrong --vault-id test_vault_id@vault-password "${TEST_FILE_1_2}"

ansible-vault decrypt "$@" --vault-id test_vault_1_2@vault-password "${TEST_FILE_1_2}"

# multiple vault passwords
ansible-vault view "$@" --vault-password-file vault-password --vault-password-file vault-password-wrong format_1_1_AES256.yml

# multiple vault passwords, --vault-id
ansible-vault view "$@" --vault-id test_vault_id@vault-password --vault-id test_vault_id@vault-password-wrong format_1_1_AES256.yml

# encrypt it, with password from password script
ansible-vault encrypt "$@" --vault-password-file password-script.py "${TEST_FILE}"

ansible-vault view "$@" --vault-password-file password-script.py "${TEST_FILE}"

ansible-vault decrypt "$@" --vault-password-file password-script.py "${TEST_FILE}"

# encrypt it, with password from password script
ansible-vault encrypt "$@" --vault-id test_vault_id@password-script.py "${TEST_FILE}"

ansible-vault view "$@" --vault-id test_vault_id@password-script.py "${TEST_FILE}"

ansible-vault decrypt "$@" --vault-id test_vault_id@password-script.py "${TEST_FILE}"

# new password file for rekeyed file
NEW_VAULT_PASSWORD="${MYTMPDIR}/new-vault-password"
echo "newpassword" > "${NEW_VAULT_PASSWORD}"

ansible-vault encrypt "$@" --vault-password-file vault-password "${TEST_FILE}"

ansible-vault rekey "$@" --vault-password-file vault-password --new-vault-password-file "${NEW_VAULT_PASSWORD}" "${TEST_FILE}"

ansible-vault view "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" "${TEST_FILE}"

# view with old password file and new password file
ansible-vault view "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" --vault-password-file vault-password "${TEST_FILE}"

# view with old password file and new password file, different order
ansible-vault view "$@" --vault-password-file vault-password --vault-password-file "${NEW_VAULT_PASSWORD}" "${TEST_FILE}"

# view with old password file and new password file and another wrong
ansible-vault view "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" --vault-password-file vault-password-wrong --vault-password-file vault-password "${TEST_FILE}"

# view with old password file and new password file and another wrong, using --vault-id
ansible-vault view "$@" --vault-id "tmp_new_password@${NEW_VAULT_PASSWORD}" --vault-id wrong_password@vault-password-wrong --vault-id myorg@vault-password "${TEST_FILE}"

ansible-vault decrypt "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" "${TEST_FILE}"

# reading/writing to/from stdin/stdin  (See https://github.com/ansible/ansible/issues/23567)
ansible-vault encrypt "$@" --vault-password-file "${VAULT_PASSWORD_FILE}" --output="${TEST_FILE_OUTPUT}" < "${TEST_FILE}"
OUTPUT=$(ansible-vault decrypt "$@" --vault-password-file "${VAULT_PASSWORD_FILE}" --output=- < "${TEST_FILE_OUTPUT}")
echo "${OUTPUT}" | grep 'This is a test file'

OUTPUT_DASH=$(ansible-vault decrypt "$@" --vault-password-file "${VAULT_PASSWORD_FILE}" --output=- "${TEST_FILE_OUTPUT}")
echo "${OUTPUT_DASH}" | grep 'This is a test file'

OUTPUT_DASH_SPACE=$(ansible-vault decrypt "$@" --vault-password-file "${VAULT_PASSWORD_FILE}" --output - "${TEST_FILE_OUTPUT}")
echo "${OUTPUT_DASH_SPACE}" | grep 'This is a test file'


# test using an empty vault password file
ansible-vault view "$@" --vault-password-file empty-password format_1_1_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

ansible-vault view "$@" --vault-id=empty@empty-password --vault-password-file empty-password format_1_1_AES256.yml && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

echo 'foo' > some_file.txt
ansible-vault encrypt "$@" --vault-password-file empty-password some_file.txt && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]


ansible-vault encrypt_string "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" "a test string"

ansible-vault encrypt_string "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" --name "blippy" "a test string names blippy"

ansible-vault encrypt_string "$@" --vault-id "${NEW_VAULT_PASSWORD}" "a test string"

ansible-vault encrypt_string "$@" --vault-id "${NEW_VAULT_PASSWORD}" --name "blippy" "a test string names blippy"


# from stdin
ansible-vault encrypt_string "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" < "${TEST_FILE}"

ansible-vault encrypt_string "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" --stdin-name "the_var_from_stdin" < "${TEST_FILE}"

# write to file
ansible-vault encrypt_string "$@" --vault-password-file "${NEW_VAULT_PASSWORD}" --name "blippy" "a test string names blippy" --output "${MYTMPDIR}/enc_string_test_file"

# test ansible-vault edit with a faux editor
ansible-vault encrypt "$@" --vault-password-file vault-password "${TEST_FILE_EDIT}"

# edit a 1.1 format with no vault-id, should stay 1.1
EDITOR=./faux-editor.py ansible-vault edit "$@" --vault-password-file vault-password "${TEST_FILE_EDIT}"
head -1 "${TEST_FILE_EDIT}" | grep "${FORMAT_1_1_HEADER}"

# edit a 1.1 format with vault-id, should stay 1.1
EDITOR=./faux-editor.py ansible-vault edit "$@" --vault-id vault_password@vault-password "${TEST_FILE_EDIT}"
head -1 "${TEST_FILE_EDIT}" | grep "${FORMAT_1_1_HEADER}"

ansible-vault encrypt "$@" --vault-id vault_password@vault-password "${TEST_FILE_EDIT2}"

# edit a 1.2 format with vault id, should keep vault id and 1.2 format
EDITOR=./faux-editor.py ansible-vault edit "$@" --vault-id vault_password@vault-password "${TEST_FILE_EDIT2}"
head -1 "${TEST_FILE_EDIT2}" | grep "${FORMAT_1_2_HEADER};vault_password"

# edit a 1.2 file with no vault-id, should keep vault id and 1.2 format
EDITOR=./faux-editor.py ansible-vault edit "$@" --vault-password-file vault-password "${TEST_FILE_EDIT2}"
head -1 "${TEST_FILE_EDIT2}" | grep "${FORMAT_1_2_HEADER};vault_password"


# test playbooks using vaulted files
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password --list-tasks
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password --list-hosts
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password --syntax-check
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password --syntax-check
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password
ansible-playbook test_vaulted_inventory.yml -i vaulted.inventory -v "$@" --vault-password-file vault-password
ansible-playbook test_vaulted_template.yml -i ../../inventory -v "$@" --vault-password-file vault-password

# test with password from password script
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file password-script.py
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file password-script.py

# with multiple password files
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password --vault-password-file vault-password-wrong
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password-wrong --vault-password-file vault-password

ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password --vault-password-file vault-password-wrong --syntax-check
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password-wrong --vault-password-file vault-password

# test with a default vault password file set in config
ANSIBLE_VAULT_PASSWORD_FILE=vault-password ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password-wrong

# test using vault_identity_list config
ANSIBLE_VAULT_IDENTITY_LIST='wrong-password@vault-password-wrong,default@vault-password' ansible-playbook test_vault.yml -i ../../inventory -v "$@"

# test that we can have a vault encrypted yaml file that includes embedded vault vars
# that were encrypted with a different vault secret
ansible-playbook test_vault_file_encrypted_embedded.yml -i ../../inventory "$@" --vault-id encrypted_file_encrypted_var_password --vault-id vault-password

# with multiple password files, --vault-id, ordering
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-id vault-password --vault-id vault-password-wrong
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-id vault-password-wrong --vault-id vault-password

ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-id vault-password --vault-id vault-password-wrong --syntax-check
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-id vault-password-wrong --vault-id vault-password

# test with multiple password files, including a script, and a wrong password
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password-wrong --vault-password-file password-script.py --vault-password-file vault-password

# test with multiple password files, including a script, and a wrong password, and a mix of --vault-id and --vault-password-file
ansible-playbook test_vault_embedded.yml -i ../../inventory -v "$@" --vault-password-file vault-password-wrong --vault-id password-script.py --vault-id vault-password

# test with multiple password files, including a script, and a wrong password, and a mix of --vault-id and --vault-password-file
ansible-playbook test_vault_embedded_ids.yml -i ../../inventory -v "$@" \
	--vault-password-file vault-password-wrong \
	--vault-id password-script.py --vault-id example1@example1_password \
	--vault-id example2@example2_password --vault-password-file example3_password \
	--vault-id vault-password

# with wrong password
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password-wrong && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# with multiple wrong passwords
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-password-file vault-password-wrong --vault-password-file vault-password-wrong && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# with wrong password, --vault-id
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-id vault-password-wrong && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# with multiple wrong passwords with --vault-id
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-id vault-password-wrong --vault-id vault-password-wrong && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# with multiple wrong passwords with --vault-id
ansible-playbook test_vault.yml          -i ../../inventory -v "$@" --vault-id wrong1@vault-password-wrong --vault-id wrong2@vault-password-wrong && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# with empty password file
ansible-playbook test_vault.yml           -i ../../inventory -v "$@" --vault-id empty@empty-password && :
WRONG_RC=$?
echo "rc was $WRONG_RC (1 is expected)"
[ $WRONG_RC -eq 1 ]

# test invalid format ala https://github.com/ansible/ansible/issues/28038
EXPECTED_ERROR='Vault format unhexlify error: Non-hexadecimal digit found'
ansible-playbook "$@" -i invalid_format/inventory --vault-id invalid_format/vault-secret invalid_format/broken-host-vars-tasks.yml 2>&1 | grep "${EXPECTED_ERROR}"

EXPECTED_ERROR='Vault format unhexlify error: Odd-length string'
ansible-playbook "$@" -i invalid_format/inventory --vault-id invalid_format/vault-secret invalid_format/broken-group-vars-tasks.yml 2>&1 | grep "${EXPECTED_ERROR}"
