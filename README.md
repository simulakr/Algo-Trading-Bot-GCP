# 📈 Algo Trading Bot (Google Cloud Virtual Machine) — BB, DC, MA and NW Strategies

## About the Project

**Algo Trading Backtest** is a Python-based automated trading bot developed to test and evaluate algorithmic trading strategies running on Google Cloud Platform (GCP). The project implements popular technical analysis strategies such as Bollinger Bands (BB), Donchian Channels (DC), Moving Averages (MA), and Nadaraya-Watson (NW), and performs backtesting processes.

## Features

* **Strategies:** Bollinger Bands, Donchian Channels, Moving Averages, Nadaraya-Watson
* **Backtesting:** Simulate strategy performance on historical data
* **Modular Design:** Strategy, signal, position management, and exchange operations in separate modules
* **Google Cloud Platform (GCP) Compatible:** Cloud deployment ready
* **Pip Requirements:** Project dependencies are listed in requirements.txt file

## File Structure

* `config.py` — Project general configurations
* `entry_strategies.py` — Entry strategy definitions
* `exit_strategies.py` — Exit strategy definitions
* `indicators.py` — Technical indicator calculations
* `signals.py` — Buy/Sell signal generation
* `position_manager.py` — Position management and risk control
* `exchange.py` — Exchange API integrations and order execution
* `main.py` — Main execution file, integrates all modules
* `.env` — Environment variables
* `requirements.txt` — Project Python dependencies

## Installation

1. Clone the repository:

```bash
git clone https://github.com/simulakr/Algo-Trading-Bot-GCP.git
cd Algo-Trading-Bot-GCP
```

2. Create and activate a virtual environment (optional but recommended):

```bash
python -m venv venv
source venv/bin/activate # Linux / macOS
venv\Scripts\activate # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Place the `.env` file in the project root directory and add API keys and other required information.

## Usage

You can start the bot by running the `main.py` file:

```bash
python main.py
```

The bot will generate entry and exit signals according to configured strategies, manage positions, and report simulation results.

## Contributing

We welcome your contributions! You can open pull requests for new strategies, bug fixes, or improvements.
