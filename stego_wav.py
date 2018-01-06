import wave
import sys
from zlib import compress, decompress 
from optparse import OptionParser
import os
import struct
import random

#Command line arguments utility functions
def validate_message(message_path):
	if not os.path.isfile(message_path):
		print "Message file does not exist!"
		sys.exit(1)
	return message_path

def validate_audio(audio_path):
	if not os.path.isfile(audio_path):
		print "Audio file does not exist!"
		sys.exit(1)
	return audio_path

#String to Binary and vice versa conversion functions
#Modified off standard code found on Google
def stringToBinary(s, b=('0000','0001','0010','0011', '0100','0101','0110','0111',
						'1000','1001','1010', '1011','1100','1101','1110','1111')):
	return "".join([b[x]+b[y] for x,y in [divmod(ord(c),16) for c in s]])

def binaryToString(b):
	bl = 8
	bitlist = map(int,''.join(b.split()))

	if len(bitlist)%bl != 0:
		return -1

	rs = ''.join([chr(sum(bit<<abs(idx-bl)-1 for idx,bit in enumerate(y)))
				for y in zip(*[bitlist[x::bl] for x in range(bl)])])
	return rs

def check_enough_frames(audio, message_bytes):
	needed_frames = audio.getnframes() / (message_bytes*8)
	if needed_frames==0:
		print "Message is too large to be stored in the cover file"
		sys.exit(-1)

def decode_message(audio_path, output_path, key):
	audio = wave.open(audio_path,"rb")
	
	#Some trickery to figure out what wave_read.tell will return at the end of the wave stream
	#Just in case it's not the same as the number of frames...
	audio.readframes(audio.getnframes()+1)
	end_file_stream = audio.tell()
	audio.rewind()

	#Seed the pseudo-random number generator
	random.seed(key)

	#Read all the frames from the stego-ed
	audio.rewind()
	buffer=[]
	for i in range(audio.getnframes()):
		buffer.append(audio.readframes(1))

	bytes_so_far=""

	#Make a dictionary of already-chosen positions
	picked={}

	while True:
		byte=""		
		for i in range(0,8):
			num = random.randint(0, end_file_stream-1)
			while num in picked:
				num = random.randint(0, end_file_stream-1)
			picked[num]=True
			binary_frame = stringToBinary(buffer[num])
			byte+=binary_frame[-1]
			if len(picked.keys())==audio.getnframes():
				break
			
		bytes_so_far+=byte
		decomp=""
		try:
			decomp = decompress(binaryToString(bytes_so_far))
			last_char=stringToBinary(decomp[-1])
		except:
			last_char=""
			
		if (last_char=="00000100") or len(picked.keys())==audio.getnframes():
			break #We've found the whole messages or we've run out of things to check
		else:
			continue #We still need to keep reading

	if len(picked.keys())==audio.getnframes() and (last_char!="00000100"):
		print "FAIL. Key was incorrect."
	else:
		output_text = open(output_path, 'w')
		output_text.write(decomp[:-1])
		output_text.close()
		print "SUCCESS. Message has been extracted to '" + output_path + "'"

def encode_message(message_path, audio_path, output_path, key):
	audio = wave.open(audio_path,"rb")
	message = open(message_path, 'rb')

	#Read the entire message into a buffer
	message.seek(0)
	message_buffer = message.read()
	message.close()

	#Append the End Of Transmission ASCII control character to the buffer
	message_buffer+= binaryToString("00000100")

	#Compress the message buffer
	message_buffer = compress(message_buffer)

	#Probably not necessary, but just in case
	audio.rewind()
	
	#Some trickery to figure out what wave_read.tell will return at the end of the wave stream
	#Just in case it's not the same as the number of frames...
	audio.readframes(audio.getnframes()+1)
	end_file_stream = audio.tell()
	audio.rewind()

	# Get the total number of bytes in the file
	message_total_bytes = len(message_buffer)
	check_enough_frames(audio, message_total_bytes)

	

	#Seed the pseudo-random number generator
	random.seed(key)

	#Read all the frames from the original file. We'll make changes to this buffer
	audio.rewind()
	output_buffer=[]
	for i in range(audio.getnframes()):
		output_buffer.append(audio.readframes(1))

	#Make a dictionary of already-chosen positions
	picked={}

	#To help with updating progress
	progress={}

	bytes_encoded = 0
	for c in message_buffer:
		bits = stringToBinary(c)
		for bit in bits:
			num = random.randint(0, end_file_stream-1)
			while (num in picked):
				num = random.randint(0, end_file_stream-1)
			picked[num] = True		
			audio.rewind()
			audio.setpos(num)
			
			current_frame = audio.readframes(1)
			
			new_frame_bits = (stringToBinary(current_frame))[:-1] + bit		

			output_buffer[num] = binaryToString(new_frame_bits)
		bytes_encoded+=1
		
		prog= ((float(bytes_encoded) / float(len(message_buffer)))*100)
		if int(prog%10)==0:
			if not ((int(prog)) in progress):
				sys.stdout.write("%3d done \n" %prog)
				sys.stdout.flush()
				progress[int(prog)]=True

	output_string=""
	for frame in output_buffer:
		output_string = output_string+frame
	output = wave.open(output_path, "wb")
	output.setparams(audio.getparams())
	output.writeframes(output_string)
	audio.close()
	output.close()
	print "Encoding done!"

if __name__ == "__main__":

	# The usage message should something go wrong.
	usage = "usage: %prog -a AUDIO_FILE -f FILE_NAME"

	parser = OptionParser(usage)
	parser.add_option("-m", "--message", help="read message from FILENAME")
	parser.add_option("-a", "--audio", help="store message in AUDIO FILE")
	
	parser.add_option("-o", "--output", help="output file")

	parser.add_option("-k", "--key", help="the key to encode/decode the message")

	parser.add_option("-d", "--decode", help="decode message in AUDIO FILE")

	(options, args) = parser.parse_args()

	# Make sure we have proper input before proceeding.

	if options.decode == None:
		message_path = validate_message(options.message)
		audio_path = validate_audio(options.audio)
		if options.output == None:
			output_path = os.path.abspath(os.curdir)+"/output.wav"
		else:
			output_path = options.output
		
		if options.key == None: #we could just as easily make a default key
			print "Need to provide a key"
			sys.exit(1)
		else:
			key = options.key
		
		encode_message(message_path, audio_path, output_path, key)
	else:
		if options.output == None:
			output_path = os.path.abspath(os.curdir)+"/decoded_message.txt"
		else:
			output_path = options.output
			
		if options.key == None:
			print "Need to provide a key"
			sys.exit(1)
		else:
			key = options.key
			
		decode_path = validate_audio(options.decode)
		decode_message(decode_path, output_path, key)
