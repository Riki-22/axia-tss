#!/bin/bash
# SageMaker環境の詳細診断

echo "=========================================="
echo "📋 環境診断レポート"
echo "=========================================="

echo -e "\n1. JupyterLabバージョン:"
jupyter lab --version

echo -e "\n2. Pythonバージョン:"
python --version

echo -e "\n3. Plotly関連パッケージ:"
pip list | grep -i plotly

echo -e "\n4. ipywidgets関連:"
pip list | grep -i widget

echo -e "\n5. 現在のConda環境:"
conda env list | grep '*'

echo -e "\n6. axia-env環境のパッケージ確認:"
conda activate axia-env 2>/dev/null && python -c "
import plotly
import ipywidgets
print(f'✅ plotly: {plotly.__version__}')
print(f'✅ ipywidgets: {ipywidgets.__version__}')
" || echo "❌ axia-env環境でのインポートエラー"

echo -e "\n7. JupyterLab拡張機能（現在）:"
jupyter labextension list

echo -e "\n8. Jupyterカーネル一覧:"
jupyter kernelspec list

echo "=========================================="