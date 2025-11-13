import streamlit as st

# Título de la aplicación
st.title("¡Hola Streamlit! 👋")

# Encabezado
st.header("Mi Primera App de Streamlit")

# Texto
st.write("Esta es una aplicación sencilla creada con Streamlit.")

# Input de texto
nombre = st.text_input("¿Cuál es tu nombre?")

if nombre:
    st.write(f"¡Hola {nombre}! Bienvenido a mi aplicación.")

# Slider
edad = st.slider("¿Cuál es tu edad?", 0, 100, 25)
st.write(f"Tu edad es: {edad}")

# Selectbox
opcion = st.selectbox(
    "¿Cuál es tu lenguaje de programación favorito?",
    ["Python", "JavaScript", "Java", "C++", "Otro"]
)
st.write(f"Has seleccionado: {opcion}")

# Checkbox
if st.checkbox("Mostrar mensaje especial"):
    st.success("¡Gracias por usar esta aplicación! 🎉")

# Botón
if st.button("Haz clic aquí"):
    st.balloons()
    st.write("¡Has presionado el botón! 🎈")
