
'''
usage: python commentLatinPairer.py *path to directory containing latin files* *path to commentary file* *path to output file*
*latin file ID* *number latin files* *english words file path*
examples: 
	Anthon: python commentLatinPairer.py files/latin/ files/comments/Anthon.txt files/output/Anthon_output BG 11 files/english/words
	Bond: python commentLatinPairer.py files/latin/ files/comments/Bond.txt files/output/Bond_output BG 11 files/english/words
	Cannon: python commentLatinPairer.py files/latin/ files/comments/Cannon.txt files/output/Cannon_output BG 11 files/english/words
	- ERROR
	Colbeck: 
	- This is a commentary on book 6; make it so that you can define the bottom of the range of books rather than the max
	Collar97:
	- This is a commentary on book 2




file system setup: this program should be run s.t. the latin files are stored like
'files/latin/BG1'
and the commentaries
'files/comments/Anthon'

input file naming: Files that are named *book identifier* *book number*, ex. BG4.
input file structure: Chapter number on one line, body of the chapter on the next

output file name: 'files/commentLatinPair'
output file structure: *latin sentence* | *comment on some subsection of the sentence*


This program takes in Latin Text (LT) and a commentary (CT), then steps through both in
sequence, matching Latin phrase to comment and outputting the pairs as pipe-
separated values in a file.

Input: Path to plain text of a latin text, path to plain text of an OCR'ed commentary concerning about this Latin.

Output: Pipe-separated key-value store in which each key is the Latin sentence and each values is the corresponding comment body

TODO: print comments out even if they don't have corresponding latin


Idea for how to counter redundancy (like, if two comments just have "atque" as their token):

# maintain an LT index pointer (LTI)

	# step through the CT line-by-line
		# tokenize the Latin Phrase (LP): split the line, step through the words one-by-one and check that they're not English or, if they are English, that they aren't in the LT set
			# Note: if it's just english, it probably got the line break wrong

		# step through the LT, comparing phrases of similar length

		# when we find a match, put the (sentence, comment body) pair in the OD. Comment body (CB) is defined as any bit of the line past the LP

		# if we don't find a match in the length of the max LT search window, increase the LTI the length of the candidate LP

'''

import re
import sys
import sets
import difflib
from nltk import tokenize
from collections import Counter
from string import printable

commentEndChars = ['.', ')', '\"', '\'', '?', '!', '\xe2\x80\x9d'] # the last one is how the OCR usually reads the closing quotation '"'


'''
strips the characters that aren't letters from a string
'''
def stripNonLetters(inputString):
	regex = re.compile('[^a-zA-Z]')
	return regex.sub('', inputString)


'''
Returns true if input can be represented as an int
'''
def RepresentsInt(s):
    try: 
        int(s)
        return True
    except ValueError:
        return False

'''
returns true if the string has letters in it
'''
def hasLetters(inputString):
	if re.search('[a-zA-Z]', inputString):
		return True
	return False


'''
Increases the latin word counter and adds to list of sentences
'''
def ingestLatin(inputFile, bookTitle, latinSentences, latinWordCount):
	with open(inputFile, 'r') as f:
		# print Counter(f.read().replace('\n', '').split())['ad']
		content = f.readlines()
		for elem in content:
			if RepresentsInt(elem) or 'BOOK' in elem:
				pass
				# latinSentences.append(bookTitle + ' SECTION ' + elem) # don't have the headings in the sentence list
			else:
				latinSentences += tokenize.sent_tokenize(elem)
				bad = [i for i in latinSentences if len(i) < 4]
				latinSentences = [item.lower() for item in latinSentences if item not in bad]
				latinWordCount += Counter(elem.split())
	return (latinWordCount, latinSentences)



def ingestInput(textName, numBooks, latinPath, commentPath, englishPath, minCommentLength=10):
	latinWordCount = Counter()
	latinSentences = []
	commentLines = []
	comments = []
	englishWords = set()

	# ingest latin
	for i in range(1, numBooks+1):
		bookTitle = textName +' BOOK '+str(i)
		latinWordCount, latinSentences = ingestLatin(latinPath + textName + str(i), bookTitle, latinSentences, latinWordCount)

	# ingest comments
	with open(commentPath, 'r') as f:
		commentLines = f.readlines()
		commentLines = [x.strip().replace('Digitized by Google', '') for x in commentLines]
		comments.append(commentLines[0])
		for line in commentLines[1:]:
			'''
			preprocess comments so that
			1. all comments end with punctuation
			2. all comments are a minumum length
			3. don't append next line if it starts with a number (because this probably means it's a new comment)
			'''
			if comments[-1][-1] not in commentEndChars or len(comments[-1]) < minCommentLength and not RepresentsInt(line.strip()[0]):
				comments[-1] += line
			else:
				comments.append(line)

	# ingest english words
	with open(englishPath, 'r') as f:
		englishWords = set(f.read().replace('\n', ' ').split())

	return (latinWordCount, latinSentences, comments, englishWords)


'''
Given a comment and the set of possible latin words, extract the part of the comment that
constites a corresponding phrase in the latin (usually the first few words)
'''
def extractToken(comment, latinWordSet, englishWords, editCutoff=0.6, maxTokenLength=3):
	latinToken = ''
	lastWord = ''
	for word in comment.split():
		lastWord = word
		if hasLetters(word):
			strippedWord = stripNonLetters(word).lower()
			if strippedWord in englishWords and strippedWord not in latinWordSet: # we've reached the english, probably
				latinToken = latinToken.strip()  # take off the last space character
				break
			else:
				simSet = difflib.get_close_matches(strippedWord, latinWordSet, n=1, cutoff=editCutoff) # get the set of most similar words from the latin
				if len(simSet) > 0:
					candidate = simSet[0] 	# pick the first word arbitrarily; TODO could be improved with ngrams
					latinToken += candidate + ' '
				else:
					latinToken = latinToken.strip()  # take off the last space character
					break 

	if len(latinToken) <= maxTokenLength:		# ignore tokens that are too short; don't have to do this if we have good tokenizing
		return ('', '')

	return (latinToken, lastWord)


'''
finds str2 in str1 and uppercases it
'''
def findAndUppercase(str1, str2):
	return str1.replace(str2, str2.upper())


'''
Runs through the list of comments and the list of latin sentences and puts
any matches in a dictionary

maxLatinSearchWindow: makes sure that we don't, like, search through the whole document
and find an incorrect match at the end and end up missing all the other matches

'''
def pairLatinComments(latinWordCount, latinSentences, commentLines, englishWords, maxLatinSearchWindow=10, printUnmatchedComments=True, minTokenLength=2, verbose=False):
	# initialize the output dictionary (OD)
	latinCommentDict = {}
	tokenSentenceDict = {} # this dict makes sure that we don't map identical tokens to the same sentences over and over
	latinWordSet = set(latinWordCount)
	unmatchedCount = 0.0 # we don't update this in implementation v1, but we could use this in conjunction with MLSW to move the pointer through the latin

	for comment in commentLines:
		# tokenize the latin phrase
		wholeToken, firstCommentWord = extractToken(comment, latinWordSet, englishWords)
		if len(wholeToken) <= 0 and printUnmatchedComments == True:
			latinCommentDict[comment] = 'NOT FOUND'  # even if we couldn't find a latin token, still print the unmatched comment
			unmatchedCount += 1
			continue
		
		for cutoff in range(len(wholeToken.split()) - minTokenLength+1):
			latinToken = wholeToken.rsplit(' ', cutoff)[0] # cut off one word each time until we find a match

			for sentence in latinSentences:
				if latinToken in sentence: # both are already lowercase
					if latinToken.upper() in tokenSentenceDict and sentence in tokenSentenceDict[latinToken.upper()]:
						# this is to avoid mapping different identical phrases to the same sentence mulitple times (like, so every comment
						# with 'atque' as the token doesn't get mapped to the same sentence; you move on to the next sentence)
						continue
					if verbose:
						print ''
						print 'wholeToken = ', wholeToken
						print 'latinToken = ', latinToken
						print "comment = ", comment
						print ''
						print 'sentence = ', sentence
						print ''
					sentence = findAndUppercase(sentence, latinToken)
					latinCommentDict[comment] = sentence # used to have comment[len(latinToken):] so that you wouldn't see the latin. could also use comment[comment.find(firstCommentWord):]]
					if latinToken.upper() in tokenSentenceDict:
						tokenSentenceDict[latinToken.upper()].add(sentence)
					else:
						tokenSentenceDict[latinToken.upper()] = set([sentence])
					foundMatch = True
					break

		if printUnmatchedComments and comment not in latinCommentDict: # if we don't have a match, print anyway
			unmatchedCount += 1
			latinCommentDict[comment] = 'NOT FOUND'	# used to have comment[len(wholeToken):] so that you wouldn't see the latin

	accuracy = (len(latinCommentDict) - unmatchedCount) / len(latinCommentDict)
	return (latinCommentDict, accuracy)


"""
Escapes quotations within strings and wraps strings in quotations.
Useful for turning into SQL bulk loading format
"""
def wrapToEscapeQuotations(string):
    string = string.replace('\"', '\"\"')
    string = '\"' + string + '\"'
    return string


'''
print the printable parts of a string
'''
def extractPrintable(word):
	result = ''
	for char in word:
		if char == '\xe2\x80\x9c' or char == '\xe2\x80\x9d': 
			pass
		elif char not in printable:
			result += '*'
		else:
			result += char
	return result


'''
Writes the comment dictionary out to a file, with the items
surrounded by quotations and separated by pipes.
'''
def writeCommentDictToFile(d, filename='output.txt'):
	f = open(filename, 'w+')
	for latin, comment in d.iteritems():
		# print "latin = ", latin
		# print "comment = ", comment
		first = extractPrintable(wrapToEscapeQuotations(comment.strip()))
		second = extractPrintable(wrapToEscapeQuotations(latin))
		f.write(first + '|' + second + '\n\n')


if __name__ == "__main__":
	if len(sys.argv) != 7:
		print ("usage: python commentLatinPairer.py *path to directory containing latin files* *path to commentary file* *path to output file*")
		quit()
	latinPath = sys.argv[1]
	commentFilePath = sys.argv[2]
	outputFilePath = sys.argv[3]
	bookID = sys.argv[4]
	numBooks = int(sys.argv[5])
	englishFilePath = sys.argv[6]
	latinWordCount, latinSentences, commentLines, englishWords = ingestInput(bookID, numBooks, latinPath, commentFilePath, englishFilePath)
	commentDict, accuracy = pairLatinComments(latinWordCount, latinSentences, commentLines, englishWords)
	print accuracy*100, '% of comments matched'
	writeCommentDictToFile(commentDict, filename=outputFilePath)







