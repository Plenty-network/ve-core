#!/usr/bin/env bash

set -e -o pipefail

echo "-------------------------------------"
echo "Compiling PLY Ve(3,3) contracts"
echo "-------------------------------------"

# Expected location of SmartPy CLI.
SMART_PY_CLI=~/smartpy-cli/SmartPy.sh

# Output directory
OUT_DIR=./test_outputs

# Compilation directory
COMP_DIR=./michelson

# Array of files to compile.
CONTRACTS_ARRAY=(ply_fa12 vote_escrow voter gauge bribe fee_distributor core_factory ve_swap)

# Ensure we have a SmartPy binary.
if [ ! -f "$SMART_PY_CLI" ]; then
    echo "Fatal: Please install SmartPy CLI at $SMART_PY_CLI" && exit
fi

# Compile a contract.
# Args <contract name, ex: minter> <invocation, ex: MinterContract()> <out dir>
function processContract {
    CONTRACT_NAME=$1
    OUT_DIR=$2
    CONTRACT_IN="${CONTRACT_NAME}.py"
    CONTRACT_OUT="${CONTRACT_NAME}.tz"
    STORAGE_OUT="${CONTRACT_NAME}_storage.tz"
    CONTRACT_COMPILED="${CONTRACT_NAME}/step_000_cont_0_contract.tz"
    STORAGE_COMPILED="${CONTRACT_NAME}/step_000_cont_0_storage.tz"

    echo ">> Processing ${CONTRACT_NAME}"

    # Ensure file exists.
    if [ ! -f "$CONTRACT_IN" ]; then
        echo "Fatal: $CONTRACT_IN not found. Running from wrong dir?" && exit
    fi

    # Test
    echo ">>> [1 / 3] Testing ${CONTRACT_NAME} "
    $SMART_PY_CLI test $CONTRACT_IN $OUT_DIR --html
    echo ">>> Done"

    echo ">>> [2 / 3] Compiling ${CONTRACT_NAME}"
    $SMART_PY_CLI compile $CONTRACT_IN $OUT_DIR
    echo ">>> Done."

    echo ">>> [3 / 3] Copying Artifacts"
    cp $OUT_DIR/$CONTRACT_COMPILED $COMP_DIR/$CONTRACT_OUT
    cp $OUT_DIR/$STORAGE_COMPILED $COMP_DIR/$STORAGE_OUT
    echo ">>> Written to ${CONTRACT_OUT} & ${STORAGE_OUT}"
}

echo "> [1 / 3] Unit Testing and Compiling Contracts."
for i in ${!CONTRACTS_ARRAY[@]}; do
    echo ">> [$((i + 1)) / ${#CONTRACTS_ARRAY[@]}] Processing ${CONTRACTS_ARRAY[$i]}"
    processContract ${CONTRACTS_ARRAY[$i]} $OUT_DIR
    echo ">> Done."
    echo ""
done
echo "> Compilation Complete."
echo ""

# Remove other artifacts to reduce noise.
echo "> [2 / 2] Cleaning up"
rm -rf $OUT_DIR
echo "> All tidied up."
echo ""

echo "----------------------------------------"
echo "Task complete."
echo "----------------------------------------"