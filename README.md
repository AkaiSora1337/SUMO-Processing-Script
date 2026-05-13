# Traffic Intersection Analysis using SUMO

## Overview

This project investigates traffic flow characteristics at a signalized intersection using SUMO simulation.

The project evaluates:
- Queue length
- Vehicle delay
- Degree of saturation
- Signal timing performance

Python was used for post-processing and visualization of simulation outputs.

---

## Simulation Environment

- SUMO version: 1.25.0
- Python version: 3.10

---

## Network Configuration

The simulation contains:
- Signalized four-leg intersection
- Multiple signal timing scenarios
- E1/E2 detectors for traffic measurement

---

## Data Processing

Simulation outputs were processed using:
- pandas
- NumPy
- matplotlib

Key metrics include:
- Average delay
- Queue length
- Traffic throughput

---

## Example Results

(Insert figures here)

---

## Repository Structure

```text
scripts/     Python analysis scripts
network/     SUMO network and route files
outputs/     Simulation outputs
report/        Reports and documentation
