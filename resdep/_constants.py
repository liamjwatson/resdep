# --- Constants
g: float = 2.0023193043609236
a_g: float = (g - 2) / 2
m_e: float = 9.109383713928e-31  # kg
c: float = 299792458  # m/s
e: float = 1.602176634e-19  # C
# * Fractional spin tune
v_s: float = 0.833  # 6.833
v_s303GeV: float = 0.879  # 6.879, based on if the beam energy is 3.0311 GeV
# End User Run Machine Parameters (2025-09-28)
v_x: float = 0.289148  # 13.29
v_y: float = 0.21626  # 5.219
v_synch: float = 0.00847

if __name__ == "__main__":
    print("This file contains numerical constants for calculations.")