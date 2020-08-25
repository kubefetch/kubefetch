#!/usr/bin/env bash

set -eu

# Using set -x for this test causes the Shippable console to stop receiving updates and the job to time out for OS X.
# Once that issue is resolved the set -x option can be added above.

# Run these using en_US.UTF-8 because list-tasks is a user output function and so it tailors its output to the
# user's locale.  For unicode tags, this means replacing non-ascii chars with "?"

COMMAND=(ansible-playbook -i ../../inventory test_tags.yml -v --list-tasks)

export LC_ALL=en_US.UTF-8

# Run everything by default
[ "$("${COMMAND[@]}" | grep -F Task_with | xargs)" = \
"Task_with_tag TAGS: [tag] Task_with_always_tag TAGS: [always] Task_with_unicode_tag TAGS: [くらとみ] Task_with_list_of_tags TAGS: [café, press] Task_without_tag TAGS: []" ]

# Run the exact tags, and always
[ "$("${COMMAND[@]}" --tags tag | grep -F Task_with | xargs)" = \
"Task_with_tag TAGS: [tag] Task_with_always_tag TAGS: [always]" ]

# Skip one tag
[ "$("${COMMAND[@]}" --skip-tags tag | grep -F Task_with | xargs)" = \
"Task_with_always_tag TAGS: [always] Task_with_unicode_tag TAGS: [くらとみ] Task_with_list_of_tags TAGS: [café, press] Task_without_tag TAGS: []" ]

# Skip a unicode tag
[ "$("${COMMAND[@]}" --skip-tags 'くらとみ' | grep -F Task_with | xargs)" = \
"Task_with_tag TAGS: [tag] Task_with_always_tag TAGS: [always] Task_with_list_of_tags TAGS: [café, press] Task_without_tag TAGS: []" ]

# Run just a unicode tag and always
[ "$("${COMMAND[@]}" --tags 'くらとみ' | grep -F Task_with | xargs)" = \
"Task_with_always_tag TAGS: [always] Task_with_unicode_tag TAGS: [くらとみ]" ]

# Run a tag from a list of tags and always
[ "$("${COMMAND[@]}" --tags café | grep -F Task_with | xargs)" = \
"Task_with_always_tag TAGS: [always] Task_with_list_of_tags TAGS: [café, press]" ]
