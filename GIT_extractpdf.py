import fitz  # PyMuPDF
import re
from openai import OpenAI


from gtts import gTTS
import os
import time
from google.cloud import texttospeech
from pydub import AudioSegment
import datetime
import sys


# Verifica que se haya proporcionado el nombre del archivo como argumento
if len(sys.argv) != 2:
    print("Uso: python GIT_extractpdf.py nombre_del_archivo.pdf")
    sys.exit(1)

nombre_archivo_pdf = sys.argv[1]  # El nombre del archivo se pasa como primer argumento

# Función para limpiar el texto
def limpiar_texto(texto):
    # Ejemplo: eliminar encabezados, pies de página, y números de página
    texto_limpio = re.sub(r'Encabezado: .*|\d+ / \d+|Página \d+', '', texto)
    return texto_limpio

def limpiar_brackets(texto):
    texto_limpio = re.sub(r'\[INICIO\]|\[MEDIO\]', '', texto)
    return texto_limpio

# Función para obtener el número de páginas del PDF
def obtener_numero_paginas(pdf_path):
    with fitz.open(pdf_path) as doc:
        return len(doc)

def contar_palabras(texto):
    # Dividir el texto en palabras
    palabras = texto.split()
    # Contar el número de palabras
    numero_palabras = len(palabras)
    return numero_palabras





# Función para calcular el tiempo estimado de procesamiento
def calcular_tiempo_estimado(numero_paginas, tiempo_conocido, paginas_conocidas):
    return (numero_paginas / paginas_conocidas) * tiempo_conocido

# Función para dividir el texto en segmentos según el límite de tokens
def dividir_texto(texto, max_length=4097):
    palabras = texto.split()
    segmentos = []
    segmento_actual = ""

    for palabra in palabras:
        if len(segmento_actual + palabra) <= max_length:
            segmento_actual += palabra + " "
        else:
            segmentos.append(segmento_actual)
            segmento_actual = palabra + " "
    segmentos.append(segmento_actual)  # Agrega el último segmento

    return segmentos

# Función para extraer texto usando OCR
def extract_text_with_ocr(pdf_path):
    doc = fitz.open(pdf_path)
    text = ''
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

# Función para dividir el texto en segmentos según el límite de tamaño
def dividir_texto_en_segmentos(texto, max_byte_size=4000):
    segmentos = []
    segmento_actual = ""
    for palabra in texto.split():
        if len((segmento_actual + palabra).encode('utf-8')) <= max_byte_size:
            segmento_actual += palabra + " "
        else:
            segmentos.append(segmento_actual)
            segmento_actual = palabra + " "
    if segmento_actual:
        segmentos.append(segmento_actual)
    return segmentos

# Función para sintetizar un segmento de texto y guardar el audio
def sintetizar_segmento(client, texto, index, voice, audio_config):
    synthesis_input = texttospeech.SynthesisInput(text=texto)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    with open(f"segmento_{index}.mp3", "wb") as out:
        out.write(response.audio_content)

start_time_total = time.time()

# Extracción de texto con OCR
ocr_text = extract_text_with_ocr(nombre_archivo_pdf)


# Obtener el número de páginas del PDF
numero_paginas = obtener_numero_paginas(nombre_archivo_pdf)

# Calcular el tiempo estimado de procesamiento
tiempo_estimado = calcular_tiempo_estimado(numero_paginas, 222, 29)
print(f"Tiempo estimado para procesar {numero_paginas} páginas: {tiempo_estimado} segundos")


# Limpieza y división del texto
texto_limpio = limpiar_texto(ocr_text)

with open('openai.txt', 'r') as file:
    api_key = file.readline().strip()

# Configura tu clave API de OpenAI
client = OpenAI(api_key=api_key)
# Prepara los datos de la solicitud

segmentos = dividir_texto(texto_limpio)

# Enviar cada segmento y concatenar las respuestas
respuesta_completa = ""
cont = 0

start_time_openai = time.time()
for segmento in segmentos:

    if(cont == 0):
        input = "[INICIO] "
        cont = 1
    else:
        input = "[MEDIO] "

    response = client.chat.completions.create(model="gpt-3.5-turbo",
    max_tokens=2500,
    messages=[
        {"role": "system", "content": "Tu trabajo es reestructurar los textos (y resumirlos si procede) que te lleguen para que posteriormente un TTS lo reproduzca correctamente, eres un servicio online llamado 'Text to teaching' si te llega un bracket [INICIO] significa que es el inicio del audio que se va a reproducir por lo que puedes dar una introducción, si te llega un bracket [MEDIO] limitate solo a reestructurar, nunca pongas en el texto los brackets inicio y medio, y siempre responde en español. Intenta no omitir información, pero si resumirla de manera que sea ameno y parezca un lenguaje natural."},
        {"role": "user", "content": input + segmento}
    ])

    # Asegúrate de acceder a la respuesta correctamente
    respuesta_completa += response.choices[0].message.content.strip()

# Imprimir la respuesta completa
respuesta_completa = limpiar_brackets(respuesta_completa)
print(respuesta_completa)
print(f"El texto tiene {contar_palabras(respuesta_completa)} palabras.")

end_time_openai = time.time()
print(f"Tiempo para procesamiento con OpenAI: {end_time_openai - start_time_openai} segundos")
# Tu texto procesado
texto_para_audio = respuesta_completa


with open("archivo.txt", "w", encoding="utf-8") as archivo:
    # Escribe el texto en el archivo
    archivo.write(respuesta_completa)

# Crear un cliente de Text-to-Speech
client = texttospeech.TextToSpeechClient()
voice = texttospeech.VoiceSelectionParams(language_code="es-ES", name="es-ES-Neural2-B", ssml_gender=texttospeech.SsmlVoiceGender.MALE)
audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

# Iniciar el contador de tiempo para la conversión de texto a voz
start_time_tts = time.time()

# Procesar cada segmento
segmentos = dividir_texto_en_segmentos(texto_para_audio)
for i, segmento in enumerate(segmentos):
    sintetizar_segmento(client, segmento, i, voice, audio_config)

# Unir los audios
audio_completo = AudioSegment.empty()
for i in range(len(segmentos)):
    segmento_audio = AudioSegment.from_mp3(f"segmento_{i}.mp3")
    audio_completo += segmento_audio
    os.remove(f"segmento_{i}.mp3")  # Opcional: eliminar el archivo segmento después de unirlo

# Obtener el timestamp actual
timestamp = datetime.datetime.now().timestamp()

audio_completo.export(str(int(timestamp)) + "-audiolibroGoogle.mp3", format="mp3", bitrate="64k")
end_time_tts = time.time()
print(f"Tiempo para conversión de texto a voz: {end_time_tts - start_time_tts} segundos")


'''
# Iniciar el contador de tiempo para la conversión de texto a voz
start_time_tts = time.time()
# Convertir texto en audio usando gTTS
tts = gTTS(texto_para_audio, lang='es')  # Asegúrate de elegir el idioma correcto
tts.save("audiolibro3.mp3")
end_time_tts = time.time()
print(f"Tiempo para conversión de texto a voz: {end_time_tts - start_time_tts} segundos")
'''
end_time_total = time.time()
print(f"Tiempo total del proceso: {end_time_total - start_time_total} segundos")

# Reproducir el audiolibro (opcional)
os.system("start " + str(int(timestamp)) + "-audiolibroGoogle.mp3")
