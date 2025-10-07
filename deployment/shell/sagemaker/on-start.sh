#!/bin/bash
set -e # エラーが発生したらスクリプトを終了

# --- ログ設定 ---
LOG_FILE="/home/sagemaker-user/lifecycle_setup.log"
exec > >(tee -a ${LOG_FILE}) 2>&1

echo "--- Lifecycle script started at $(date) ---"

# --- メイン処理をバックグラウンドで実行 ---
(
    # Condaの初期化
    source /opt/conda/bin/activate base

    # --- 1. 古いカーネル設定のクリーンアップ ---
    echo "Cleaning up old Jupyter kernel specs if they exist..."
    KERNEL_DIR="/home/sagemaker-user/.local/share/jupyter/kernels/axia-env"
    if [ -d "$KERNEL_DIR" ]; then
        rm -rfv "$KERNEL_DIR"
    fi
    echo "Cleanup finished."

    # --- 2. Conda環境の構築 ---
    ENV_NAME="axia-env"
    YML_PATH="/home/sagemaker-user/TradingStrategySystem/src/infrastructure/aws/sagemaker/jupyterlab/environment.yml"
    
    echo "Updating or creating conda environment '$ENV_NAME'..."
    conda env update --name "$ENV_NAME" --file "$YML_PATH" --prune
    echo "Conda environment setup finished."

    # --- 3. 新しいJupyterカーネルの設定 ---
    # これ以降のコマンドはaxia-env環境内で実行する
    source /opt/conda/bin/activate "$ENV_NAME"
    
    echo "Setting up new Jupyter kernel spec from within '$ENV_NAME'..."
    python -m ipykernel install --user --name "$ENV_NAME" --display-name "Python ($ENV_NAME)"
    echo "Kernel setup finished."

    # --- 4. JupyterLab拡張機能の再ビルド（より安全な方法） ---
    # 'jupyter lab clean --all' は削除。'build'コマンドが必要なクリーンアップを自動で行います。
    echo "Rebuilding JupyterLab extensions to ensure compatibility..."
    jupyter lab build --minimize=False
    echo "JupyterLab build finished."
    
    # 環境を非アクティブ化
    conda deactivate

    echo "--- Background setup process finished successfully at $(date) ---"

) &

exit 0
