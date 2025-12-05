import streamlit as st
import json
import time
from datetime import datetime

DATA_FILE = "orders.json"

def load_orders():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_orders(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

st.title("🍱 KantinGo – Pesan Makanan Tanpa Antre")

menu = ["Nasi Goreng", "Ayam Geprek", "Mie Ayam", "Es Teh", "Kopi Susu"]
name = st.text_input("Nama Mahasiswa")
choice = st.selectbox("Pilih Menu", menu)
submit = st.button("Pesan Sekarang")

if submit:
    if name == "":
        st.warning("Nama harus diisi!")
    else:
        orders = load_orders()
        new_order = {
            "nama": name,
            "menu": choice,
            "status": "Diproses",
            "waktu": datetime.now().strftime("%H:%M:%S")
        }
        orders.append(new_order)
        save_orders(orders)
        st.success("Pesanan berhasil dibuat!")

st.subheader("📢 Status Pesanan")
orders = load_orders()
for o in orders:
    st.write(f"{o['nama']} – {o['menu']} – **{o['status']}** ({o['waktu']})")
