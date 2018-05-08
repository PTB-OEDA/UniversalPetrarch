# -*- coding: utf-8 -*-
import networkx as nx
import PETRglobals
import PETRreader
import logging
import utilities
import sys
if sys.version[0] == '2':
    from sets import Set


class NounPhrase:

    def __init__(self, sentence, npIDs, headID, date):

        self.npIDs = npIDs
        self.text = ""
        self.head = None
        self.headID = headID
        self.meaning = ""
        self.date = date
        self.sentence = sentence
        self.matched_txt = None
        self.prep_phrase = []

    def get_meaning(self):
        logger = logging.getLogger('petr_log.NPgetmeaning')

        # 1. matching the main part of noun phrase string in the actor or agent dictionary
        # main part is extracted by removing all the prepositional phrases in
        # the noun phrase

        # npMainText = self.text
        # for prep_phrase in self.prep_phrase:
        #	logger.debug("pphrase:"+prep_phrase.text)
        #	npMainText = npMainText.replace(prep_phrase.text,"")

        # find direct modifiers of noun head, remove preposition phrases
        direct_modifier_ids = []
        for successor in self.sentence.udgraph.successors(self.headID):
            relation = self.sentence.udgraph[
                self.headID][successor]['relation']
            if relation in ['amod', 'compound', 'det', 'name'] or relation.startswith("nmod"):
                direct_modifier_ids.append(successor)
                direct_modifier_ids.extend(
                    self.sentence.udgraph.successors(successor))

        direct_modifier_ids.sort()
        # print(direct_modifier_ids)

        npMainTextIds = []
        npMainTextIds.extend(direct_modifier_ids)
        npMainTextIds.append(self.headID)
        npMainTextIds.sort()
        npMainTokens = []
        for npID in range(npMainTextIds[0], min(npMainTextIds[-1], self.npIDs[-1]) + 1):
            npMainTokens.append(self.sentence.udgraph.node[npID]['token'])
        npMainText = (" ").join(npMainTokens)
        # print(self.text)
        # print(npMainTextIds)
        if npMainText not in self.text:
            npMainText = self.text
            # print(npMainText)

        logger.debug("npMainText:" + npMainText)
        codes, roots, matched_txt = self.textMatching(
            npMainText.upper().split(" "))
        actorcodes, agentcodes = self.resolve_codes(codes)
        logger.debug("actorcodes:" + (",").join(actorcodes))
        logger.debug("agentcodes:" + (",").join(agentcodes))
        if actorcodes or agentcodes:
            # if both actor and agent are found, return the code
            self.meaning = self.mix_codes(agentcodes, actorcodes)
            self.matched_txt = matched_txt
            logger.debug("npMainText meaning:" + (",").join(self.meaning))
            return codes, roots, matched_txt

        # 2. if actor code is not found, matching the entire noun phrase string
        # in the actor or agent dictionary
        npText = self.text.upper().split(" ")
        codes, roots, matched_txt = self.textMatching(npText)

        actorcodes, agentcodes = self.resolve_codes(codes)
        self.meaning = self.mix_codes(agentcodes, actorcodes)
        self.matched_txt = matched_txt

        return codes, roots, matched_txt

    def textMatching(self, npText):
        codes = []
        roots = []
        matched_txt = []

        index = 0
        while index < len(npText):

            match = self.code_extraction(PETRglobals.ActorDict, npText[
                                         index:], 0)  # checking for actors
            if match:
                # --                print('NPgm-m-1:',match)
                codes += match[0]
                roots += match[3]
                index += match[2]
                matched_txt += [match[1]]
        # --                print('NPgm-1:',matched_txt)
                break

            index += 1

        index = 0
        while index < len(npText):

            match = self.code_extraction(PETRglobals.AgentDict, npText[
                                         index:], 0)  # checking for agents

            if match:
                # --                print('NPgm-2.0:',roots)
                codes += match[0]
                roots += [['~']]
                index += match[2]
                matched_txt += [match[1]]
                """print('NPgm-2:',matched_txt) # --
                print('NPgm-2.1:',roots)"""
            
            index += 1
        return codes, roots, matched_txt

    def code_extraction(self, path, words, length, so_far=""):
        """ this method returns the code of noun phrase string in the actor or agent dictionary
        """
        # --            print('NPgm-rec-lev:',len(getouterframes(currentframe(1))))  # --

        if words and words[0] in path:
            match = self.code_extraction(
                path[words[0]], words[1:], length + 1, so_far + " " + words[0])
            if match:
                return match

        if '#' in path:
            if isinstance(path["#"], list):
                code = self.check_date(path['#'])
                if not code is None:

                    # --                         print('NPgm-rec-1:',code)  # --
                    # --                         print('NPgm-rec-1.1:',path['#'][-1])
                    # 16.04.25 this branch always resolves to an actor;
                    # path['#'][-1] is the root string
                    return [code], so_far, length, [path['#'][-1]]
            else:
                # --                    print('NPgm-rec-2:',path['#'])
                # 16.04.25 this branch always resolves to an agent
                return [path['#']], so_far, length
        return False

    def resolve_codes(self, codes):
        """
        Method that divides a list of mixed codes into actor and agent codes

        Parameters
        -----------
        codes: list
               Mixed list of codes

        Returns
        -------
        actorcodes: list
                    List of actor codes

        agentcodes: list
                    List of actor codes

        """
        if not codes:
            return [], []

        actorcodes = []
        agentcodes = []
        for code in codes:
            if not code:
                continue
            if code.startswith("~") or code.endswith("~"):
                agentcodes.append(code)
            else:
                actorcodes.append(code)

        actorcodes = list(set(actorcodes))
        agentcodes = list(set(agentcodes))
        return actorcodes, agentcodes

    def mix_codes(self, agents, actors):
        """
        Combine the actor codes and agent codes addressing duplicates
        and removing the general "~PPL" if there's a better option.

        Parameters
        -----------
        agents, actors : Lists of their respective codes


        Returns
        -------
        codes: list
               [Agent codes] x [Actor codes]

        """

        # --        print('mc-entry',actors,agents)

        def mix(a, b):
            if not b[1:] in a[-len(b[1:]):] and b[0] in '~':
                # handle agents such as "~GOV"
                return a + b[1:]
            elif not b[:-1] in a[0:len(b[:-1])] and b[-1] in '~':
                # handle agents such as "NGO~"
                return b[:-1] + a
            else:
                return a

        codes = set()
        actors = actors if actors else ['~']
        for ag in agents:
            if ag == '~PPL' and len(agents) > 1:
                continue
        #            actors = map( lambda a : mix( a[0], ag[1:]), actors)
            actors = map(lambda a: mix(a, ag), actors)

        # --        print('mc-1',actors)
        for code in filter(lambda a: a not in ['', '~', '~~', None], actors):
            codes.add(code)
        return list(codes)

        # 16.04.25 hmmm, this is either a construct of utterly phenomenal
        # subtlety or else we never hit this code...
        codes = set()
        # --        print('WTF-1')
        for act in (actors if actors else ['~']):
            for ag in (agents if agents else ['~']):
                if ag == "~PPL" and len(agents) > 1:
                    continue
                code = act
                if not ag[1:] in act:
                    code += ag[1:]
                if not code in ['~', '~~', ""]:
                    codes.add(code)
        return list(codes)

    def check_date(self, match):
        """
        Method for resolving date restrictions on actor codes.

        Parameters
        -----------
        match: list
               Dates and codes from the dictionary

        Returns
        -------
        code: string
              The code corresponding to how the actor should be coded given the date


        Note <16.06.10 pas>
        -------------------
        In a very small set of cases involving a reflexive PRP inside a PP, the system can get into an infinite
        recursion where it first backs up a couple levels from the (PP, then this call to child.get_meaning() drops
        back down to the same point via the two child invocations in NounPhrase.get_meaning()

                    elif child.label == "PP":
                        m = self.resolve_codes(child.get_meaning())

        and in PrepPhrase.get_meaning()

                    self.meaning = self.children[1].get_meaning() if isinstance(self.children[1],NounPhrase) else ""

        which takes one back to the same point at one deeper level of recursion. These structures occurred about five times
        in a 20M sentence corpus, and I couldn't find any fix that didn't break something else, so I just trapped it
        here.

        There are a bunch of commented-out debugging prints remaining from this futile pursuit that could presumably be
        removed at some point.

        The full record for one of the offending cases is:

        <Sentence date = "20150824" id ="e35ef55a-fa30-4c34-baae-965dea33d8d8_3" source = "ANOTHER INFINITE RECURSION" sentence = "True">
        <Text>
        He started out at the bottom of the Hollywood rung, directed his own movie and managed to get noticed by Steven
        Spielberg himself to nab a tiny role in 1998s Saving Private Ryan .
        </Text>
        <Parse>
        (ROOT (S (S (NP (PRP He))
        (VP (VBD started) (PRT (RP out))
        (PP (IN at)
        (NP (NP (DT the) (NN bottom))
        (PP (IN of) (NP (DT the) (NNP Hollywood) ))))))
        (VP (VBD rung))
        (, ,)
        (S (VP
        (VP (VBD directed) (NP (PRP$ his) (JJ own) (NN movie))) (CC and)
        (VP (VBD managed) (S
        (VP (TO to)
        (VP (VB get)
            (VP (VBN noticed)
            (PP (IN by)
                (NP (NNP Steven) (NNP Spielberg) (PRP himself))
            )
            (S  (VP (TO to)  (VP (VB nab)
                    (NP (NP (DT a) (JJ tiny) (NN role))
                    (PP (IN in)
                        (NP (NP (NNS 1998s))  (VP (VBG Saving)  (NP (JJ Private) (NNP Ryan))
                    ))))))))))))))
        (. .)))
        </Parse>
        </Sentence>

        """

        finalcode = None
        nodatecode = None
        matched_code = []

        #curdate = self.date
        #print("curdate:"+ str(curdate))
        # print(PETRreader.ordate_to_dstr(curdate))
        # try:
        for j in match:
            dates = j[1]
            date = []
            code = ""
            for d in dates:
                if d[0] in '<>':
                    date.append(d[0] + str(PETRreader.dstr_to_ordate(d[1:])))
                else:
                    date.append(str(PETRreader.dstr_to_ordate(d)))

            curdate = self.date

            # print(("\n").join(date))
            #print("curdate:"+ str(self.date))

            if not date:
                nodatecode = j[0]
            elif len(date) == 1:
                if date[0][0] == '<':
                    if curdate <= int(date[0][1:]):
                        code = j[0]
                        matched_code.append(j)
                else:
                    if curdate >= int(date[0][1:]):
                        code = j[0]
                        matched_code.append(j)
            else:
                if curdate <= int(date[1]):
                    if curdate >= int(date[0]):
                        code = j[0]
                        matched_code.append(j)

        if len(matched_code) > 1:
            # two cases:
            # 1. embedded time restrictions: pick the smaller one
            # 2. multiple same restrictions: pick the first one
            best_date = ""
            best_code = ""
            best_date_range = float('inf')
            for item in matched_code:
                #print("matched:" + item[0] + "\t" + (" ").join(item[1]))
                date = item[1]
                if len(date) == 2:
                    date_range = PETRreader.dstr_to_ordate(
                        date[1]) - PETRreader.dstr_to_ordate(date[0])
                    if date_range < best_date_range:
                        best_date_range = date_range
                        best_code = item[0]
                        best_date = date

            finalcode = best_code
        elif len(matched_code) == 1:
            finalcode = matched_code[0][0]

        if not finalcode and nodatecode:
            finalcode = nodatecode

        # print("finalcode:"+finalcode)
        return finalcode


class PrepPhrase:

    def __init__(self, sentence, ppIDs):

        self.ppIDs = ppIDs
        self.text = ""


class VerbPhrase:

    def __init__(self, sentence, vpIDs, headID):

        self.vpIDs = vpIDs
        self.text = ""
        self.rawtext = ""
        self.head = None
        self.headID = headID
        self.verbIDs = []
        self.meaning = ""
        self.sentence = sentence
        self.code = None
        self.passive = False
        self.negative = False


class Sentence:
    """
Holds the information of a sentence and its dependency tree.


Methods
-------

__init__ : Initialization and instantiation

str_to_graph: Reads UD parse into memory
    """

    def __init__(self, parse, text, date):
        """
Initialization for Sentence classes.


Parameters
-----------

parse: string
       parse tree read from input file

date: string
verbs: dictionary
       verb phrases in the sentence
       key is the headID in the dependency parse tree graph, value is a VerbPhrase object
nouns: dictionary
       noun phrases in the sentence
       key is the headID in the dependency parse tree graph, value is a NounPhrase object

udgraph: graph
                 store denpendency parse tree as a graph

        verbIDs: list
                         store the token ID of all verbs in the sentence

Returns
-------
An instantiated Sentence object

"""
        self.parse = parse
        #self.agent = ""
        self.ID = -1
        #self.actor = ""
        self.date = date
        self.longlat = (-1, -1)
        self.verbs = {}
        self.nouns = {}
        self.triplets = {}
        self.rootID = []
        self.verbIDs = []
        self.txt = text
        self.udgraph = self.str_to_graph(parse)
        #self.verb_analysis = {}
        self.events = {}
        self.metadata = {'nouns': [], 'verbs': [], 'triplets': []}

    def str_to_graph(self, str):
        dpgraph = nx.DiGraph()
        parsed = self.parse.split("\n")
        # print(parsed)

        dpgraph.add_node(0, token='ROOT', pos='ROOT', lemma='ROOT')
        for p in parsed:
            temp = p.split("\t")

            # print(temp)
            dpgraph.add_node(int(temp[0]), token=temp[
                             1], pos=temp[3], lemma=temp[2])
            dpgraph.add_edge(int(temp[6]), int(temp[0]), relation=temp[7])

        return dpgraph

    def get_rootNode(self):
        rootID = []
        # find the head verbs of the sentence
        for successor in self.udgraph.successors(0):
            # if('relation' in self.udgraph[0][successor]):
                # print(self.udgraph[nodeID][successor]['relation'])
            if self.udgraph[0][successor]['relation'] in ['root']:
                root = successor
                # if the root node is a verb, add it directly and find whether
                # any conjunctive verb exists
                if self.udgraph.node[root]['pos'] == 'VERB':
                    rootID.append(root)

                else:
                    # if the root node is not a verb
                    # if a copula relation exist, find the verb connected to
                    # the root, and use the verb as root
                    for rsuccessor in self.udgraph.successors(root):
                        if self.udgraph[root][rsuccessor]['relation'] != 'cop' and self.udgraph.node[rsuccessor]['pos'] == 'VERB':
                            rootID.append(rsuccessor)
                            #raw_input('root is not verb')

                # raw_input("roots: "+("#").join(str(x) for x in self.rootID))

                # found other root nodes from parallel relation ('conj' &
                # 'parataxis')
                rsuccessors = self.udgraph.successors(root)
                for rsuccessor in rsuccessors:
                    if self.udgraph[root][rsuccessor]['relation'] in ['conj', 'parataxis']:
                        rootID.append(rsuccessor)

                # raw_input("roots: "+("#").join(str(x) for x in self.rootID))

        # raw_input("roots: "+("#").join(str(x) for x in self.rootID))
        return rootID

    def get_nounPharse(self, nounhead):
        """
                Extract noun phrase given the head of the phrase
                Note: this function now is used for Petrarch 1 pattern matching only

        """
        logger = logging.getLogger('petr_log.getNP')
        npIDs = []
        prep_phrase = []
        if(self.udgraph.node[nounhead]['pos'] in ['NOUN', 'ADJ', 'PROPN']):
            allsuccessors = nx.dfs_successors(self.udgraph, nounhead)

            parents = [nounhead]

            while len(parents) > 0:
                temp = []
                '''ignore the conjunt nouns'''
                for parent in parents:
                    if parent in allsuccessors.keys():
                        for child in allsuccessors[parent]:
                            if parent != nounhead or self.udgraph[parent][child]['relation'] not in ['cc', 'conj']:
                                npIDs.append(child)
                                temp.append(child)
                               
                            if parent == nounhead and self.udgraph[nounhead][child]['relation'] in ['nmod']:
                                # extract prepositional phrases in a noun phrase
                                # logger.debug(self.udgraph[nounhead][child]['relation'])
                                # logger.debug(self.udgraph.node[nounhead])
                                nmod_successors = nx.dfs_successors(
                                    self.udgraph, child)

                                pptemp = []
                                pptemp.append(child)
                                for key in nmod_successors.keys():
                                    pptemp.extend(nmod_successors[key])
                                pptemp.sort()
                                logger.debug(pptemp)
                                if self.udgraph.node[pptemp[0]]['pos'] in ['ADP']:

                                    prep_phrase.append(pptemp)

                parents = temp

            '''
			for parent,child in allsuccessors.items():
				print(str(parent))
				print(child)
			'''

            # for value in allsuccessors.values():
            #	npIDs.extend(value)
            # print(npIDs)

        npIDs.append(nounhead)
        npTokens = []
        npIDs.sort()
        # print(npIDs)
        if self.udgraph.node[npIDs[0]]['pos'] == 'ADP':
            npIDs = npIDs[1:]
        for npID in npIDs:
            npTokens.append(self.udgraph.node[npID]['token'])

        nounPhrasetext = (' ').join(npTokens)

        np = NounPhrase(self, npIDs, nounhead, self.date)
        np.text = nounPhrasetext
        np.head = self.udgraph.node[nounhead]['token']

        logger.debug("noun:" + nounPhrasetext)
        for pp in prep_phrase:
            ppTokens = []
            for ppID in pp:
                ppTokens.append(self.udgraph.node[ppID]['token'])

            pptext = (' ').join(ppTokens)
            pphrase = PrepPhrase(self, pp)
            pphrase.text = pptext
            np.prep_phrase.append(pphrase)

            logger.debug(pptext)

        return np

    def get_nounPharses(self, nounhead):
        """
                Extract noun phrases given the head of the phrase.
                It is an extension of funciton get_nounPharse()
                1. If conjunctions are found in the modifiers, split the noun phrases into several noun phrases.
                e.g. "the ambassadors of Arnor, Osgiliath and Gondor"
                three noun phrases will be generated: the ambassadors of Arnor, the ambassadors of Osgiliath , the ambassadors of Gondor"

                2. apply modifier to each conjunctive nouns
                e.g. "Lawmakers and officials in Arnor"
                two noun phrases will be generated: lawmakers in Arnor, officials in Arnor

        """
        nps = []

        logger = logging.getLogger('petr_log.getNP')

        nmod_conjs = {}
        npIDs = []
        prep_phrase = []
        if(self.udgraph.node[nounhead]['pos'] in ['NOUN', 'ADJ', 'PROPN', 'PRON']):
            allsuccessors = nx.dfs_successors(self.udgraph, nounhead)

            flag = True
            parents = [nounhead]

            while len(parents) > 0:
                temp = []
                '''ignore the conjunt nouns'''
                parentgen = (
                    parent for parent in parents if parent in allsuccessors.keys())
                for parent in parentgen:
                    for child in allsuccessors[parent]:
                        if parent != nounhead or self.udgraph[parent][child]['relation'] not in ['cc', 'conj']:

                            # find noun modifiers conjuctions
                            if self.udgraph[parent][child]['relation'] in ['nmod']:
                                nmod_conjs[child] = []
                                if child in allsuccessors.keys():
                                    for nmodchild in allsuccessors[child]:
                                        if self.udgraph[child][nmodchild]['relation'] in ['conj']:
                                            if self.udgraph.node[nmodchild]['pos'] in ['NOUN', 'PROPN']:

                                                nmod_conjs[child].append(
                                                    nmodchild)

                            temp.append(child)

                            if parent in nmod_conjs and child in nmod_conjs[parent]:
                                print(str(parent) + ":" + str(child))
                            else:
                                npIDs.append(child)

                parents = temp

            parents = [nounhead]
            while len(parents) > 0:
                temp = []

                parentgen = (
                    parent for parent in parents if parent in allsuccessors.keys())

                for parent in parentgen:
                    for child in allsuccessors[parent]:
                        if parent != nounhead or self.udgraph[parent][child]['relation'] not in ['cc', 'conj']:
                            temp.append(child)

                        if parent == nounhead and self.udgraph[nounhead][child]['relation'] in ['nmod']:
                            # extract prepositional phrases in a noun phrase
                            nmod_successors = nx.dfs_successors(
                                self.udgraph, child)

                            pptemp = []
                            pptemp.append(child)
                            for key in nmod_successors.keys():
                                pptemp.extend(nmod_successors[key])
                            pptemp.sort()
                            logger.debug(pptemp)
                            if self.udgraph.node[pptemp[0]]['pos'] in ['ADP']:

                                prep_phrase.append(pptemp)

                parents = temp

            '''
			for parent,child in allsuccessors.items():
				print(str(parent))
				print(child)
			'''
            '''

			for nmod,nmodchildren in nmod_conjs.items():
				print("nmod:"+str(nmod)+":"+self.udgraph.node[nmod]['token'])
				for nmodchild in nmodchildren:
					print("nmodchild:"+str(nmodchild)+":"+self.udgraph.node[nmodchild]['token'])
			'''

            # if len(nmodchildren)>0:
            #raw_input(" compound nous")

        npIDs.append(nounhead)
        npTokens = []
        npIDs.sort()
        # print(npIDs)
        # if self.udgraph.node[npIDs[0]]['pos']=='ADP':
        #	npIDs = npIDs[1:]
        for npID in npIDs:
            npTokens.append(self.udgraph.node[npID]['token'])

        nounPhrasetext = (' ').join(npTokens)
        logger.debug("noun:" + nounPhrasetext)

        np = NounPhrase(self, npIDs, nounhead, self.date)
        np.text = nounPhrasetext
        np.head = self.udgraph.node[nounhead]['token']

        for pp in prep_phrase:
            ppTokens = []
            for ppID in pp:
                ppTokens.append(self.udgraph.node[ppID]['token'])

            pptext = (' ').join(ppTokens)
            pphrase = PrepPhrase(self, pp)
            pphrase.text = pptext
            np.prep_phrase.append(pphrase)

            logger.debug(pptext)

        nps.append(np)

        for nmod, nmodchildren in nmod_conjs.items():
            logger.debug("nmod:" + str(nmod) + ":" +
                         self.udgraph.node[nmod]['token'])
            for nmodchild in nmodchildren:
                logger.debug("nmodchild:" + str(nmodchild) + ":" +
                             self.udgraph.node[nmodchild]['token'])
                conjnpIDs = []
                conjnpTokens = []
                for npID in npIDs:
                    if npID in self.udgraph[nmod] and self.udgraph[nmod][npID]['relation'] in ['name', "compound"]:
                        continue

                    if npID == nmod:
                        conjnpIDs.append(nmodchild)
                        conjnpTokens.append(
                            self.udgraph.node[nmodchild]['token'])
                    else:
                        conjnpIDs.append(npID)
                        conjnpTokens.append(self.udgraph.node[npID]['token'])

                conjnounPhrasetext = (' ').join(conjnpTokens)
                logger.debug("conjnoun:" + conjnounPhrasetext)

                conjnp = NounPhrase(self, conjnpIDs, nounhead, self.date)
                conjnp.text = conjnounPhrasetext
                conjnp.head = self.udgraph.node[nounhead]['token']
                conjnp.prep_phrase = np.prep_phrase
                nps.append(conjnp)

        self.metadata['nouns'].extend(nps)
        return nps

    def get_verbPhrase(self, verbhead):

        vpIDs = []
        self.verbIDs.append(verbhead)

        vp = VerbPhrase(self, vpIDs, verbhead)
        vp.verbIDs.append(verbhead)

        for successor in self.udgraph.successors(verbhead):
            if('relation' in self.udgraph[verbhead][successor]):
                # print(self.udgraph[nodeID][successor]['relation'])
                if self.udgraph[verbhead][successor]['relation'].startswith('compound'):
                    vpIDs.append(successor)
                if self.udgraph[verbhead][successor]['relation'].startswith('neg'):
                    vp.negative = True
                '''
				if self.udgraph[verbhead][successor]['relation'].startswith('advcl'):
					# check the to + verb structure
					if self.udgraph.node[successor]['pos']=="VERB":
						for ss in self.udgraph.successors(successor):
							if self.udgraph[successor][ss]['relation'].startswith('mark') and self.udgraph.node[ss]['pos']=='PART':
								vpIDs.append(successor)
								vpIDs.append(ss)
								self.verbIDs.append(successor)
								vp.verbIDs.append(successor)
				'''

        vpIDs.append(verbhead)
        vpTokens = []
        vpTokensraw = []
        vpIDs.sort()
        for vpID in vpIDs:
            vpTokensraw.append(self.udgraph.node[vpID]['token'])
            vpTokens.append(self.udgraph.node[vpID]['lemma'])

        verbPhrasetext = (' ').join(vpTokens)

        vp.text = verbPhrasetext
        vp.rawtext = (' ').join(vpTokensraw)
        vp.head = self.udgraph.node[verbhead]['lemma']

        return vp

    def get_source_target(self, verbIDs):
        logger = logging.getLogger("petr_log.get_source_target")

        def resolve_pronoun(pronounID, verbID, pronounrole):
            predecessors = self.udgraph.predecessors(verbID)
            for predecessor in predecessors:
                if 'relation' in self.udgraph[predecessor][verbID] and self.udgraph[predecessor][verbID]['relation'] in ['ccomp']:
                    logger.debug("resolve pronoun: found the governer of ccomp verb:" +
                                 self.udgraph.node[predecessor]['token'])
                    psource, ptarget, pothernoun = self.get_source_target([
                                                                          predecessor])
                    if pronounrole in ['source']:
                        logger.debug(
                            "resolve pronoun: found resolved source:" + str(len(psource)))
                        return psource

            return []

        source = []
        target = []
        othernoun = []
        for verbID in verbIDs:
            for successor in self.udgraph.successors(verbID):
                # print(str(verbID)+"\t"+str(successor)+"\t"+self.udgraph.node[successor]['pos'])
                if('relation' in self.udgraph[verbID][successor]):
                    # print(self.udgraph[nodeID][successor]['relation'])
                    if(self.udgraph[verbID][successor]['relation'] == 'nsubj'):
                        # source.append(self.get_nounPharse(successor))
                        if self.udgraph.node[successor]['pos'] in ['PRON']:
                            source.extend(resolve_pronoun(
                                successor, verbID, 'source'))
                        else:
                            source.extend(self.get_nounPharses(successor))
                            source.extend(self.get_conj_noun(successor))

                    elif(self.udgraph[verbID][successor]['relation'] in ['obj', 'dobj', 'iobj', 'nsubjpass']):
                        # target.append(self.get_nounPharse(successor))
                        target.extend(self.get_nounPharses(successor))
                        target.extend(self.get_conj_noun(successor))
                        if self.udgraph[verbID][successor]['relation'] in ['nsubjpass']:
                            self.verbs[verbID].passive = True

                    elif(self.udgraph[verbID][successor]['relation'] in ['nmod']):
                        # othernoun.append(self.get_nounPharse(successor))
                        othernoun.extend(self.get_nounPharses(successor))
                        othernoun.extend(self.get_conj_noun(successor))

        return source, target, othernoun

    def get_conj_noun(self, nodeID):
        """ method for extracting other conjunt nouns of this noun
                for example: Brazil and the United States, 
                Given the nodeID of Brazil, it will return noun phrase object of "the United States"

                apply modifier to each conjunctive nouns
                e.g. "Lawmakers and officials in Arnor"
                two noun phrases will be generated: lawmakers in Arnor, officials in Arnor
        """
        conj_noun = []
        for successor in self.udgraph.successors(nodeID):
            if(self.udgraph[nodeID][successor]['relation'] == 'conj'):
                # conj_noun.append(self.get_nounPharse(successor))
                conjnouns = self.get_nounPharses(successor)

                for noun in self.metadata['nouns']:
                    # find predecessors, move the modifier from its predecessor
                    if noun.headID == nodeID:
                        for conjnoun in conjnouns:
                            conjnoun.prep_phrase.extend(noun.prep_phrase)
                            for prep in conjnoun.prep_phrase:
                                conjnoun.npIDs.extend(prep.ppIDs)

                            tempprepset = set(conjnoun.prep_phrase)
                            conjnoun.prep_phrase = list(tempprepset)

                            tempIDset = set(conjnoun.npIDs)
                            conjnoun.npIDs = list(tempIDset)
                            conjnoun.npIDs.sort()
                            # print(conjnoun.prep_phrase)
                            npTokens = []
                            for npID in conjnoun.npIDs:
                                npTokens.append(
                                    self.udgraph.node[npID]['token'])

                            nntext = (' ').join(npTokens)
                            conjnoun.text = nntext

                conj_noun.extend(conjnouns)

        return conj_noun

    def get_phrases(self):
        logger = logging.getLogger("petr_log.getPhrase")
        for node in self.udgraph.nodes(data=True):
            nodeID = node[0]
            attrs = node[1]

            # if nodeID in self.verbIDs:
            # continue

            if 'pos' in attrs and attrs['pos'] == 'VERB':

                #print(str(nodeID)+"\t"+attrs['pos']+"\t"+(" ").join(str(e) for e in self.udgraph.successors(nodeID)))
                # print(self.udgraph.successors(nodeID))
                verb = self.get_verbPhrase(nodeID)
                logger.debug("extracting verb:" + verb.text)
                # if verb.headID in self.verbs:
                #	raw_input("verb:"+self.verbs[verb.headID].text)
                # else:
                #	self.verbs[verb.headID] = verb
                if verb.headID not in self.verbs:
                    self.verbs[verb.headID] = verb

                source, target, othernoun = self.get_source_target(
                    verb.verbIDs)

                # check for conjuncting verbs
                predecessors = self.udgraph.predecessors(verb.headID)
                for predecessor in predecessors:
                    if 'relation' in self.udgraph[predecessor][verb.headID] and self.udgraph[predecessor][verb.headID]['relation'] in ['conj'] and self.udgraph.node[predecessor]['pos'] == 'VERB':
                        logger.debug("found conj verb:" +
                                     self.udgraph.node[predecessor]['token'])
                        psource, ptarget, pothernoun = self.get_source_target([
                                                                              predecessor])
                        source.extend(psource)

                # find the subject for 'xcomp' relation
                # An open clausal complement (xcomp) of a verb or an adjective is a predicative or clausal complement without its own subject.
                # The reference of the subject is necessarily determined by an argument external to the xcomp
                #(normally by the object of the next higher clause, if there is one, or else by the subject of the next higher clause).
                for predecessor in predecessors:
                    if 'relation' in self.udgraph[predecessor][verb.headID] and self.udgraph[predecessor][verb.headID]['relation'] in ['xcomp']:
                        logger.debug("found the governer of xcomp verb:" +
                                     self.udgraph.node[predecessor]['token'])
                        psource, ptarget, pothernoun = self.get_source_target([
                                                                              predecessor])
                        if len(ptarget) > 0:
                            source.extend(ptarget)
                        elif len(psource) > 0:
                            source.extend(psource)
                        #raw_input("find xcomp relation")

                # find targets from the subjects of subordinate clause
                for successor in self.udgraph.successors(verb.headID):
                    if 'relation' in self.udgraph[verb.headID][successor] and self.udgraph[verb.headID][successor]['relation'] in ['ccomp']:
                        cverb = self.get_verbPhrase(successor)
                        # if cverb in self.verbs:
                        # raw_input("verb:"+self.verbs[successor])
                        # raw_input("verb:"+self.verbs[successor].text)
                        # else:
                        #	self.verbs[successor] = cverb

                        if cverb not in self.verbs:
                            self.verbs[successor] = cverb

                        logger.debug("found the ccomp verb:" +
                                     self.udgraph.node[successor]['token'])
                        ssource, starget, sothernoun = self.get_source_target([
                                                                              successor])
                        if len(ssource) > 0:
                            target.extend(ssource)

                #for t in target: print(t)
                if len(source) == 0 and len(target) > 0:
                    for t in target:
                        triplet = ("-", t, verb)
                        self.metadata['triplets'].append(triplet)
                        # self.triplet["-#"+str(t.headID)+"#"+str(verb.headID)]
                        # = triplet
                elif len(source) > 0 and len(target) == 0:
                    for s in source:
                        triplet = (s, "-", verb)
                        self.metadata['triplets'].append(triplet)
                else:
                    for s in source:
                        for t in target:
                            triplet = (s, t, verb)
                            self.metadata['triplets'].append(triplet)

                # othernoun are usually prepositional phrase, combine the verb and preposition as the new verb phrase
                # make the noun phrase in prepositional phrase as new target
                # improvement is still needed
                if len(othernoun) > 0:
                    for o in othernoun:
                        if self.udgraph.node[o.npIDs[0]]['pos'] == 'ADP':
                            vpTokens = []
                            vpTokensraw = []
                            vpIDs = []
                            vpIDs.extend(verb.vpIDs)
                            vpIDs.append(o.npIDs[0])
                            vpIDs.sort()

                            newverb = VerbPhrase(self, vpIDs, verb.headID)
                            for vpID in vpIDs:
                                vpTokensraw.append(
                                    self.udgraph.node[vpID]['token'])
                                vpTokens.append(
                                    self.udgraph.node[vpID]['lemma'])

                            verbPhrasetext = (' ').join(vpTokens)

                            newverb.text = verbPhrasetext
                            newverb.rawtext = (' ').join(vpTokensraw)
                            newverb.head = verb.head
                            newverb.passive = verb.passive
                            newverb.negative = verb.negative
                            logger.debug("construct new vp:" + newverb.text)

                            newnoun = NounPhrase(
                                self, o.npIDs[1:], o.headID, o.date)
                            targetTokens = []
                            for tID in newnoun.npIDs:
                                targetTokens.append(
                                    self.udgraph.node[tID]['token'])
                            newnoun.text = (' ').join(targetTokens)
                            newnoun.head = o.head
                            newnoun.prep_phrase = o.prep_phrase
                            if newverb.passive == False:
                                newtarget = newnoun
                                logger.debug(
                                    "construct new target:" + newtarget.text)

                                if len(source) == 0:
                                    triplet = ("-", newtarget, newverb)
                                    self.metadata['triplets'].append(triplet)
                                else:
                                    for s in source:
                                        triplet = (s, newtarget, newverb)
                                        self.metadata[
                                            'triplets'].append(triplet)

                            else:
                                newsource = newnoun
                                logger.debug(
                                    "construct new source:" + newsource.text)

                                if len(target) == 0:
                                    triplet = (newsource, '-', newverb)
                                    self.metadata['triplets'].append(triplet)
                                else:
                                    for t in target:
                                        triplet = (newsource, t, newverb)
                                        self.metadata[
                                            'triplets'].append(triplet)

                            # if the noun has conjunction, build a new triplet
                            # using the verb and conjunction
                            for successor in self.udgraph.successors(o.headID):
                                if 'relation' in self.udgraph[o.headID][successor] and self.udgraph[o.headID][successor]['relation'] in ['conj']:

                                    newconjnpids = o.npIDs[1:]
                                    headidx = newconjnpids.index(o.headID)
                                    newconjnpids[headidx] = successor
                                    newconjnpids.sort()
                                    newconjnoun = NounPhrase(
                                        self, newconjnpids, successor, o.date)
                                    tokens = []
                                    for tID in newconjnoun.npIDs:
                                        tokens.append(
                                            self.udgraph.node[tID]['token'])
                                    newconjnoun.text = (' ').join(tokens)
                                    newconjnoun.head = self.udgraph.node[
                                        newconjnoun.headID]['token']
                                    newconjnoun.prep_phrase = o.prep_phrase

                                    if newverb.passive == False:
                                        newtarget = newconjnoun
                                        logger.debug(
                                            "construct new target:" + newtarget.text)

                                        if len(source) == 0:
                                            triplet = ("-", newtarget, newverb)
                                            self.metadata[
                                                'triplets'].append(triplet)
                                        else:
                                            for s in source:
                                                triplet = (
                                                    s, newtarget, newverb)
                                                self.metadata[
                                                    'triplets'].append(triplet)

                                    else:
                                        newsource = newconjnoun
                                        logger.debug(
                                            "construct new source:" + newsource.text)

                                        if len(target) == 0:
                                            triplet = (newsource, '-', newverb)
                                            self.metadata[
                                                'triplets'].append(triplet)
                                        else:
                                            for t in target:
                                                triplet = (
                                                    newsource, t, newverb)
                                                self.metadata[
                                                    'triplets'].append(triplet)

                                    #raw_input("found conjective other noun")
                self.metadata['verbs'].append(verb)
                # self.metadata['nouns'].extend(source)
                # self.metadata['nouns'].extend(target)
                # self.metadata['nouns'].extend(othernoun)

    def get_verb_code(self):
        logger = logging.getLogger('petr_log.PETRgraph')

        def match_phrase(path, noun_phrase):
            # Having matched the head of the phrase, this matches the full noun
            # phrase, if specified
            logger.debug("mphrase-entry")
            if not noun_phrase:
                return False

            cfound = True
            match = ""
            for npID in filter(lambda a: a != noun_phrase.headID, noun_phrase.npIDs):
                nptoken = self.udgraph.node[npID]['token'].upper()
                nplemma = self.udgraph.node[npID]['lemma'].upper()

                logger.debug(str(npID) + " " + nptoken + " " + str(cfound))

                barfound = False
                if '-' in path and cfound:
                    path = path['-']
                    barfound = True
                if '|' in path:
                    path = path['|']

                logger.debug(path)
                if nptoken in path:
                    subpath = path[nptoken]
                    logger.debug(subpath)

                    cfound = True
                    match = reroute(subpath, lambda a: match_phrase(a, None))
                    # if match:
                    # return match

                    path = subpath
                elif nplemma in path:
                    subpath = path[nplemma]
                    logger.debug(subpath)

                    cfound = True
                    match = reroute(subpath, lambda a: match_phrase(a, None))
                    # if match:
                    # return match

                    path = subpath
                else:
                    cfound = False

            if match:
                return match

            return reroute(path, lambda a: match_phrase(a, noun_phrase))

        # def match_continus_noun(path,noun_phrase,start_ID):

        def match_noun(path, noun_phrase):
            logger.debug("mn-entry")

            if not isinstance(noun_phrase, basestring):
                logger.debug("noun:" + noun_phrase.head +
                             "#" + noun_phrase.text)
                head = noun_phrase.head.upper()
                headlemma = self.udgraph.node[
                    noun_phrase.headID]['lemma'].upper()
                if head in path:
                    subpath = path[head]
                    logger.debug(head + " found in pattern dictionary")
                    match = reroute(subpath, (lambda a: match_phrase(
                        a, noun_phrase)) if isinstance(noun_phrase, NounPhrase) else None)
                    if match:
                        logger.debug(match)
                        return match
                elif headlemma in path:
                    subpath = path[headlemma]
                    logger.debug(
                        headlemma + " found in pattern dictionary (lemma)")
                    match = reroute(subpath, (lambda a: match_phrase(
                        a, noun_phrase)) if isinstance(noun_phrase, NounPhrase) else None)
                    if match:
                        logger.debug(match)
                        return match

            if "$" in path:
                #print("$ "+path)
                temppath = path["$"]
                if "#" in temppath:
                    match = temppath['#']
                    if match:
                        logger.debug(match)
                        return match

            if "#" in path:
                match = path['#']
                if match:
                    logger.debug(match)
                    return match

        def match_prep(path, prep_phrase):
            print("mp-entry")

        def reroute(subpath, o1=match_noun, o2=match_noun, o3=match_prep, o4=match_noun, exit=1):
            # print('rr-entry:') # ,subpath
            if not o1:  # match_noun() can call reroute() with o1 == None; guessing returning False is the appropriate response pas 16.04.21
                return False
            if '-' in subpath:
                match = o1(subpath['-'])
                if match:
                    #print('rr-- match')
                    # print(match)
                    return match

            if '$' in subpath:
                # print('rr$ found')
                match = reroute(subpath['$'], True)
                if match:
                    # print('rr$ match')
                    return match

            if ',' in subpath:
                # print('rr-,')
                # print(subpath[','])
                match = reroute(subpath[','], True)
                if match:
                    # print(match)
                    return match

            if '|' in subpath:
                print('rr-|')
                # print(subpath['|'])
                #raw_input("match preposition")
                #match = o3(subpath['|'])
                # if match:
                #    print(match)
                #    return match

            if '*' in subpath:
                print('rr-*')
                # print(subpath['*'])
                # return subpath['*']
                #match = o4(subpath['*'])
                # if match:
                #	print(match)
                #	return match

            if '#' in subpath and exit:
                # print('rr-#')
                # print(subpath['#'])
                return subpath['#']

            # print('rr-False')
            return False

        def match_lower(path, verb, target):
            match = False
            if '*' in path:
                path = path['*']
                logger.debug("'*' matched")

            if "$" in path:
                path = path["$"]
                logger.debug("'$' matched")

            if len(verb.vpIDs) > 1:
                logger.debug("matching prep:")
                temppatternDictPath = path
                found = False
                if '|' in temppatternDictPath:
                    logger.debug("'|' matched")
                    temppatternDictPath = temppatternDictPath['|']
                    for vpID in verb.vpIDs:
                        if(vpID <= verb.headID):
                            continue
                        if self.udgraph.node[vpID]['pos'] == 'ADP' and self.udgraph.node[vpID]['token'].upper() in temppatternDictPath:
                            temppatternDictPath = temppatternDictPath[
                                self.udgraph.node[vpID]['token'].upper()]
                            logger.debug(
                                "prep matched:" + self.udgraph.node[vpID]['token'].upper())
                            found = True

                if found == True:
                    path = temppatternDictPath
                    if '#' in path:
                        path = path['#']
                        match = path
                    if '-' in path:
                        path = path['-']

                if match:
                    code = match['code']
                    matched_pattern = match['line']
                    logger.debug("matched:" + code + "\t" + matched_pattern)

            logger.debug("processing target:")
            targetmatch = match_noun(path, target)

            if targetmatch:
                return targetmatch
            elif match:
                return match
            else:
                return False

        for triple in self.metadata['triplets']:
            source = triple[0]
            target = triple[1]
            verb = triple[2]

            '''get code from verb dictionary'''
            logger.debug("finding code of verb:" + verb.text)
            verbDictionary = PETRglobals.VerbDict['verbs']
            verbDictPath = verbDictionary
            code = None
            meaning = None
            matched_txt = []

            codes = []
            meanings = []
            matched_txts = []

            verbtokens = verb.text.upper().split(" ")
            for vidx in range(0, len(verbtokens)):
                verbtext = verbtokens[vidx]
                logger.debug("match vp token:" + verbtext)
                if verbtext in verbDictPath:
                    matched_txt = []
                    tempverbDictPath = verbDictPath[verbtext]
                    matched_txt.append(verbtext)

                    for j in range(vidx, len(verbtokens)):
                        if verbtokens[j] in tempverbDictPath:
                            tempverbDictPath = tempverbDictPath[verbtokens[j]]
                            matched_txt.append(verbtokens[j])

                    if "#" in tempverbDictPath:
                        try:
                            for item in tempverbDictPath['#']['#']:
                                # code = tempverbDictPath['#']['#']['code']
                                # meaning =
                                # tempverbDictPath['#']['#']['meaning']
                                code = item['code']
                                meaning = item['meaning']

                                if (code != None and meaning != None):
                                    codes.append(code)
                                    meanings.append(meaning)
                                    matched_txts.append(matched_txt)
                        except:
                            print("passing:" + verb.text)
                            pass

                    if (code != None and meaning != None):
                        codes.append(code)
                        meanings.append(meaning)
                        matched_txts.append(matched_txt)

            if(len(verbtokens) > 1):
                logger.debug(codes)
                logger.debug(meanings)
                logger.debug(matched_txts)
                #raw_input("verb pharse has length large than 1")

            if code != None and meaning != None:
                logger.debug(code + "\t" + meaning + "\t" + verb.text + "\t" +
                             (" ").join(matched_txt) + "\t" + str(len(verb.vpIDs)))
            else:
                logger.debug("None code and none meaning")

            '''get code from pattern dictionary'''
            patternDictionary = PETRglobals.VerbDict['phrases']
            patternDictPath = patternDictionary
            matched_pattern = None
            for m in meanings:
                patternDictPath = patternDictionary
                if m in patternDictionary:
                    patternDictPath = patternDictPath[m]
                    logger.debug("processing source:")
                    match = match_noun(patternDictPath, source)
                    if match:
                        code = match['code']
                        matched_pattern = match['line']
                        logger.debug("matched:" + code +
                                     "\t" + matched_pattern)

                    pairmatch = False
                    if '%' in patternDictPath:
                        temppatternDictPath = patternDictPath['%']
                        logger.debug("'%' matched")
                        pairmatch = match_lower(
                            temppatternDictPath, verb, target)
                        if pairmatch:
                            code = pairmatch['code']
                            matched_pattern = pairmatch['line']
                            logger.debug("pair matched:" + code +
                                         "\t" + matched_pattern)

                    if '+' in patternDictPath:
                        temppatternDictPath = patternDictPath['+']
                        logger.debug("'+' matched")
                        match = match_lower(temppatternDictPath, verb, target)
                        if match:
                            code = match['code']
                            matched_pattern = match['line']
                            logger.debug("matched:" + code +
                                         "\t" + matched_pattern)

                    lowermatch = match_lower(patternDictPath, verb, target)

                    if pairmatch and "(" in pairmatch['line']:
                        match = pairmatch
                    elif lowermatch and "(" in lowermatch['line']:
                        match = lowermatch
                    elif pairmatch:
                        match = pairmatch
                    elif lowermatch:
                        match = lowermatch

                    '''
					if '*' in patternDictPath:
						patternDictPath = patternDictPath['*']
						logger.debug("'*' matched")


					if len(verb.vpIDs)>1:
						logger.debug("matching prep:")
						temppatternDictPath = patternDictPath
						found = False
						if '|' in temppatternDictPath:
							logger.debug("'|' matched")
							temppatternDictPath = temppatternDictPath['|']
							for vpID in verb.vpIDs:
								if(vpID <= verb.headID):
									continue
								if self.udgraph.node[vpID]['pos']=='ADP' and self.udgraph.node[vpID]['token'].upper() in temppatternDictPath:
									temppatternDictPath = temppatternDictPath[self.udgraph.node[vpID]['token'].upper()]
									logger.debug("prep matched:"+self.udgraph.node[vpID]['token'].upper())
									found = True

						if found==True:
							patternDictPath = temppatternDictPath
							if '#' in patternDictPath:
								patternDictPath = patternDictPath['#']
								match = patternDictPath
							if '-' in patternDictPath:
								patternDictPath = patternDictPath['-']


						if match:
							code = match['code']
							matched_pattern = match['line']
							logger.debug("matched:"+code+"\t"+matched_pattern)


					logger.debug("processing target:")
					match = match_noun(patternDictPath,target)
					'''
                    if match:
                        code = match['code']
                        matched_pattern = match['line']
                        # switch source and target
                        newsource = '-'
                        newtarget = '-'

                        if not verb.passive and "+" in matched_pattern and matched_pattern.index("+") < matched_pattern.index("*"):
                            newsource = target
                            logger.debug(
                                "+ in pattern, switch target to source")

                        if not verb.passive and "$" in matched_pattern and matched_pattern.index("$") > matched_pattern.index("*"):
                            newtarget = source
                            logger.debug(
                                "$ in pattern, switch source to target")

                        logger.debug("matched:" + code +
                                     "\t" + matched_pattern)

                        source = newsource if not isinstance(
                            newsource, basestring) else source
                        target = newtarget if not isinstance(
                            newtarget, basestring) else target

            tripleID = ('-' if isinstance(source, basestring) else str(source.headID)) + '#' + \
                       ('-' if isinstance(target, basestring) else str(target.headID)) + '#' + \
                str(verb.headID) + "#" + str(len(self.triplets))
            newtriple = (source, target, verb)

            if code != None:
                if len(code.split(":")) == 2:
                    active_code, passive_code = code.split(":")
                    if verb.passive == True:
                        verbcode = passive_code
                    else:
                        verbcode = active_code
                else:
                    verbcode = code
                if verb.negative == True:
                    #raw_input("before negated:"+verbcode)
                    if verbcode not in ['-', '---'] and int(verbcode) <= 200:
                        # validation verbs have codes over 200, add this
                        # condition to make sure the program is not crashed.
                        tempcode = utilities.convert_code(verbcode)[0] - 0xFFFF
                        tempverbcode = str(utilities.convert_code(tempcode, 0))
                        logger.debug("negated:" + verbcode +
                                     "\thex:" + hex(tempcode))
                        if tempverbcode == "0":
                            verbcode = verbcode + "#" + hex(tempcode)
                        else:
                            verbcode = tempverbcode
                        #raw_input("find negated verb:")

            else:
                verbcode = None

            self.triplets[tripleID] = {}
            self.triplets[tripleID]['triple'] = newtriple
            self.triplets[tripleID]['verbcode'] = verbcode
            self.triplets[tripleID][
                'matched_txt'] = matched_pattern if matched_pattern != None else (" ").join(matched_txt)
            self.triplets[tripleID]['meaning'] = (",").join(meanings)

            #raw_input("Press Enter to continue...")

    def get_events(self):
        logger = logging.getLogger('petr_log.PETRgraph')
        self.get_phrases()
        self.filter_triplet_with_time_expression()
        self.get_verb_code()
        self.rootID = self.get_rootNode()

        root_event = {}
        root_eventID = {}
        events = {}

        paired_event = {}

        for tripleID, triple in self.triplets.items():
            logger.debug("check event:" + tripleID)

            source = triple['triple'][0]
            target = triple['triple'][1]

            # Test of %, if % in pattern, and no target is found, PETRARCH
            # generates a paired event coded on a compound
            if '%' in triple['matched_txt'] and (not target or not isinstance(target, basestring) or target == '-'):
                paired_event[tripleID] = triple
                # continue

            source_meaning = ''
            if not isinstance(source, basestring):
                source.get_meaning()
                source_meaning = source.meaning if source.meaning != None else ''
                logger.debug("source: " + source.head + " code: " +
                             (("#").join(source.meaning) if source.meaning != None else '-'))
                self.nouns[source.headID] = source

            target_meaning = ['---']
            if not isinstance(target, basestring):
                target.get_meaning()
                target_meaning = target.meaning if target.meaning != None else [
                    '---']
                logger.debug("target: " + target.head + " code: " +
                             (("#").join(target.meaning) if target.meaning != None else '-'))
                self.nouns[target.headID] = target

            verb = triple['triple'][2]

            if verb.headID in self.rootID and tripleID not in paired_event:
                if verb.headID in root_eventID:
                    root_event[verb.headID][tripleID] = ([s.replace('~', '---') for s in source_meaning], [
                                                         t.replace('~', '---') for t in target_meaning], triple['verbcode'])
                    root_eventID[verb.headID].append(tripleID)
                else:
                    root_event[verb.headID] = {}
                    root_event[verb.headID][tripleID] = ([s.replace('~', '---') for s in source_meaning], [
                                                         t.replace('~', '---') for t in target_meaning], triple['verbcode'])
                    root_eventID[verb.headID] = [tripleID]
                logger.debug("Root verb:" + verb.text + " code:" +
                             (triple['verbcode'] if triple['verbcode'] != None else "-"))
            else:
                logger.debug("verb:" + verb.text + " code:" +
                             (triple['verbcode'] if triple['verbcode'] != None else "-"))
                #rootNeighbours = []
                # for root in self.rootID:
                #	rootNeighbours.extend(self.udgraph.neighbors(root))
                # if verb.headID in rootNeighbours:
                #	relation_with_root = self.udgraph[self.rootID][verb.headID]['relation']
                #	logger.debug("verb:"+verb.text+" relation:"+relation_with_root)

            event = ([s.replace('~', '---') for s in source_meaning],
                     [t.replace('~', '---') for t in target_meaning], triple['verbcode'])
            logger.debug(event)

            events[tripleID] = event
            triple['event'] = event

        logger.debug("event transformation....")

        if len(root_event) == 0:
            logger.debug("root_event is None")
            # return {}

        for tripleID, triple in self.triplets.items():
            if tripleID in paired_event:
                continue

            verb = triple['triple'][2]

            if len(root_event) == 0:
                self.events[tripleID] = []
                self.events[tripleID] = (list(triple['event']))

            for root in self.rootID:
                if root not in root_event:
                    continue

                if verb.headID in self.udgraph.neighbors(root):
                    relation_with_root = self.udgraph[
                        root][verb.headID]['relation']
                    if relation_with_root in ['advcl', 'ccomp', 'xcomp']:
                        current_event = triple['event']  # 4.27
                        #(source_meaning,target_meaning,triple['verbcode'])
                        logger.debug("root" + str(root))
                        for reventID, revent in root_event[root].items():
                            event_before_transfer = (
                                revent[0], current_event, revent[2])
                            if revent[0] not in ['---']:
                                event_after_transfer = self.match_transform(
                                    event_before_transfer)
                                current_eventID = tripleID

                            elif current_event[0] and current_event[1]:
                                event_after_transfer = [current_event]
                                current_eventID = tripleID

                            else:
                                event_after_transfer = [event_before_transfer]
                                current_eventID = reventID

                            logger.debug("event" + tripleID +
                                         "transformation:")
                            logger.debug(event_after_transfer)

                            for e in event_after_transfer:
                                if isinstance(e, tuple) and not isinstance(e[1], tuple):
                                    if current_eventID not in self.events:
                                        self.events[current_eventID] = []
                                        self.events[
                                            current_eventID].extend(list(e))
                                    else:
                                        logger.debug(reventID + " repeated")
                                        tempID = reventID
                                        while tempID in self.events:
                                            tempID = tempID + "0"
                                        self.events[tempID] = []
                                        self.events[tempID].extend(list(e))

                                elif isinstance(e, tuple) and isinstance(e[1], tuple) and e[2] == None and e[1][2] != None:
                                    if tripleID not in self.events:
                                        self.events[tripleID] = []
                                        self.events[tripleID].extend(
                                            list(e[1]))

        logger.debug("self.events: " + str(len(self.events)))
        for key, value in self.events.items():
            logger.debug(key + ":")
            logger.debug(value)

        if(len(self.events) == 0):
            for root in root_eventID:
                for eventID in root_eventID[root]:
                    self.events[eventID] = []
                    self.events[eventID].extend(root_event[root][eventID])

        # check the verb codes
        '''
		finalverbs = {}
		for eventID in self.events:
			if eventID not in self.triplets:
				continue

			triplet = self.triplets[eventID]
			ids = eventID.split("#")
			vid = ids[2]

			if len(self.events[eventID])!=3:
				raw_input(self.events[eventID])
				continue

			if vid not in finalverbs:
				finalverbs[vid] = self.events[eventID][2]
			else:
				logger.debug(self.events[eventID][1])
				#if len(self.events[eventID][1])==0 and self.events[eventID][2] not in ['---',None,'None']:
				#and self.events[evnetID][2] != PETRglobals.VerbDict['verbs'][triplet['meaning']]['#']['#']['code'] :
				if self.events[eventID][2] not in ['---',None,'None'] and triplet['triple'][2].head.upper() in PETRglobals.VerbDict['verbs'] and (self.events[eventID][2] != code['code'] for code in PETRglobals.VerbDict['verbs'][triplet['triple'][2].head.upper()]['#']['#']):
				#PETRglobals.VerbDict['verbs'][triplet['meaning']]['#']['#']['code']:
					finalverbs[vid] = self.events[eventID][2]

		for vid,value in finalverbs.items():
			if value != None:
				logger.debug("vid: "+vid+"\t"+str(value))
			else:
				logger.debug("vid: "+vid+"\tNone")

		for eventID in self.events:
			ids = eventID.split("#")
			vid = ids[2]
			self.events[eventID][2] = finalverbs[vid]
		'''

        # handle paired event, add comments
        allactors = {}
        for tripleID, triple in paired_event.items():
            logger.debug("paired_event:" + tripleID)
            logger.debug(triple['event'])
            verbcode = triple['event'][2]
            ids = tripleID.split("#")
            if verbcode not in allactors:
                allactors[verbcode] = {}
                allactors[verbcode]['vid'] = ids[2]
            allactors[verbcode][ids[0]] = triple['event'][0]

        for verbcode, actors in allactors.items():
            idx = len(self.events)
            for sid in actors.keys():
                for tid in actors.keys():
                    if sid != tid and sid != 'vid' and tid != 'vid':
                        tripleID = sid + "#" + tid + "#" + \
                            actors['vid'] + "#" + str(idx)
                        self.events[tripleID] = [
                            actors[sid], actors[tid], verbcode]
                        idx = idx + 1

        return self.events

    def match_transform(self, e):
        """
        Check to see if the event e follows one of the verb transformation patterns
        specified at the bottom of the Verb Dictionary file.

        If the transformation is present, adjust the event accordingly.
        If no transformation is present, check if the event is of the form:

                        1. a ( b . Q ) P , where Q is not a top-level verb.
                        2. a ( a b Q ) P , where Q is not a top-level verb.
                        3. a ( [] b Q ) P , where Q is not a top-level verb.

                and then convert this to ( a b P+Q )

        Otherwise, return the event as-is.

        Parameters
        -----------
        e: tuple
           Event to be transformed

        Returns
        -------
        t: list of tuples, matched_transformation if exist
           List of modified events, since multiple events can come from one single event
        """

        logger = logging.getLogger('petr_log.PETRgraph')

        def recurse(pdict, event, a2v={}, v2a={}):
            '''
            Parameters
            -----------
            a2v: dictionary
                     actor to variable mapping

            v2a: dictionary
                     variable to actor mapping

            '''
            logger.debug("recurse entry..")

            path = pdict
            if isinstance(pdict, list):
                # transfromation pattern is found
                line = pdict[1]
                path = pdict[0]
                verb = utilities.convert_code(path[2])[0] if not path[
                    2] == "Q" else v2a["Q"]
                if isinstance(v2a[path[1]], tuple):
                    results = []
                    for item in v2a[path[1]]:
                        results.append((list(v2a[path[0]]), item, verb))
                    logger.debug("line:" + line)
                    return results, line
                logger.debug("line:" + line)
                return [(list(v2a[path[0]]), v2a[path[1]], verb)], line

            if isinstance(event, tuple):
                if e[2] in [None, '---']:
                    return False
                # print(event)
                actor = None if not event[0] else tuple(event[0])
                # print(actor)
                eventcode = utilities.convert_code(event[2])[0]
                # , eventcode - eventcode % 0x10,eventcode - eventcode % 0x100, eventcode - eventcode % 0x1000]
                codelist = [eventcode]
                # print(eventcode)
                # print(pdict)
                # print(codelist)
                masks = filter(lambda a: a in pdict, codelist)

                # print(masks)
                logger.debug("actor:")
                logger.debug(actor)

                logger.debug("masks:")
                logger.debug(masks)

                if masks:
                    # print(masks)
                    path = pdict[masks[0]]
                elif -1 in pdict:
                    v2a["Q"] = event[2]
                    path = pdict[-1]
                    # print(path)
                else:
                    #print("nothing is found")
                    return False
            else:
                actor = event

            if actor in a2v:
                actor = a2v[actor]

            if not actor:
                actor = "_"

            logger.debug("actor:")
            logger.debug(actor)
            if actor in path:
                return recurse(path[actor], event[1], a2v, v2a)
            elif not actor == '_':
                for var in sorted(path.keys())[::-1]:
                    if var in v2a:
                        continue
                    if not var == '.':
                        v2a[var] = actor
                        a2v[actor] = var
                    return recurse(path[var], event[1], a2v, v2a)

            #logger.debug("no transformation is present")

            return False

        logger.debug("match_transform entry...")

        try:
            logger.debug(e)

            t = recurse(PETRglobals.VerbDict['transformations'], e)
            if t:
                logger.debug("transformation is present:")
                logger.debug("t:")
                logger.debug(t)
                return t
            else:
                logger.debug("no transformation is present:")
                #c = utilities.convert_code(e[1][2])[0]
                # print(c)
                #print(16 ** 3)
                #print(c / (16 ** 3))
                # not e[1][2] / (16 ** 3):
                if e[0] and e[2] and isinstance(e[1], tuple) and e[1][0] and e[1][2] and e[0] != e[1][0]:
                    logger.debug(utilities.convert_code(e[2])[0])
                    logger.debug(e[2])

                    logger.debug("the event is of the form: a ( b . Q ) P")
                    if isinstance(e[1][0], list):
                        results = []
                        for item in e[1][0]:
                            code_combined = utilities.combine_code(utilities.convert_code(e[2])[
                                                                   0], utilities.convert_code(e[1][2])[0])
                            #target = []
                            # target.append(item)
                            event = (e[0], [item], utilities.convert_code(
                                code_combined, 0))
                            logger.debug(event)
                            results.append(event)
                        return results

                    code_combined = utilities.combine_code(utilities.convert_code(e[2])[
                                                           0], utilities.convert_code(e[1][2])[0])
                    event = (e[0], [e[1][0]],
                             utilities.convert_code(code_combined, 0))
                    logger.debug(event)
                    return [event]
                elif e[0] and isinstance(e[1], tuple) and e[1][0] and e[1][2] and e[0] == e[1][0]:

                    logger.debug("the event is of the form: a ( a b Q ) P")
                    if e[2] in [None, '---']:
                        code_combined = utilities.convert_code(e[1][2])[0]
                    else:
                        code_combined = utilities.combine_code(utilities.convert_code(e[2])[
                                                               0], utilities.convert_code(e[1][2])[0])
                    event = (e[0], e[1][1], utilities.convert_code(
                        code_combined, 0))
                    logger.debug(event)

                    return [event]
                elif e[0] and isinstance(e[1], tuple) and not e[1][0] and e[1][2]:
                    logger.debug("the event is of the form: a ( [] b Q ) P")
                    if e[2] in [None, '---']:
                        code_combined = utilities.convert_code(e[1][2])[0]
                    else:
                        code_combined = utilities.combine_code(utilities.convert_code(e[2])[
                                                               0], utilities.convert_code(e[1][2])[0])
                    event = (e[0], e[1][1], utilities.convert_code(
                        code_combined, 0))
                    logger.debug(event)

                    return[event]

        except Exception as ex:
            pass  # print(ex)
        return [e]

    def filter_triplet_with_time_expression(self):
        # filter out triplet containing time expressions as target
        # only works for English now
        timeexps = Set(['Monday', 'Tuesday', 'Wednesday',
                        'Thursday', 'Friday', 'Saturday', 'Sunday'])

        def has_time_expression(triplet):
            target = triplet[1]
            if target == "-":
                return False

            if target.text in timeexps:
                return True
            else:
                return False

        self.metadata['triplets'] = [t for t in self.metadata[
            'triplets'] if not has_time_expression(t)]

    def get_upper_seq(self, kword, nouns, compound_nouns):
        """
        Generate the upper sequence starting from kword; Upper sequence currently
        terminated by clause boundary.
        The upper sequence is in reversed order 

        Note: this function now is used for Petrarch 1 pattern matching only

        """
        UpperSeq = []

        nounEndStart = {}  # key is end idx, value is start idx
        for noun in nouns:
            # print(noun.npIDs)
            # print(noun.text)
            # handle overlapped noun phrases
            # e.g. "A court in Guyana", "Guyana", choose "A court in Guyana"

            if noun.npIDs[-1] in nounEndStart.keys():
                old_range = noun.npIDs[-1] - \
                    nounEndStart[noun.npIDs[-1]]['start']
                new_range = noun.npIDs[-1] - noun.npIDs[0]
                if new_range < old_range:
                    continue

            found_overlap = False
            for end, value in nounEndStart.items():
                # print(end, value['start'])
                if noun.npIDs[0] >= value['start'] and noun.npIDs[-1] <= end:
                    found_overlap = True
                    break

            # print(found_overlap)
            if found_overlap:
                continue

            nounEndStart[noun.npIDs[-1]] = {}
            nounEndStart[noun.npIDs[-1]]['start'] = noun.npIDs[0]
            nounEndStart[noun.npIDs[-1]]['noun'] = noun

        compoundEndStart = {} # key is end idx, value is start idx
        for compound in compound_nouns:
            compoundEndStart[compound[1]] = compound[0]


        nounmark = False
        nounstart = kword
        currnoun = None
        ccount = 0
        cstart = kword
        cmark = False

        while kword >= 1:  # 1 is the index of first word in the sentence, 0 is "ROOT"
            if kword in compoundEndStart.keys():
                ccount += 1
                UpperSeq.append("~NEC" + str(ccount))
                cstart = compoundEndStart[kword]
                cmark = True


            if kword in nounEndStart.keys():
                UpperSeq.append("~NE")
                nounmark = True
                nounstart = nounEndStart[kword]['start']
                currnoun = nounEndStart[kword]['noun']
                # print("kword", kword, "start", nounstart)

            UpperSeq.append(self.udgraph.node[kword]['token'].upper())
            if nounmark and kword == nounstart:
                noun_meaning_list = [
                    "---"] if currnoun.meaning == [] else currnoun.meaning
                noun_meaning = ("#").join(noun_meaning_list)
                UpperSeq.append("(NE<" + str(kword) + ">" + noun_meaning)
                nounmark = False
                nounstart = kword
                currnoun = None
            # else:
            # 	UpperSeq.append(self.udgraph.node[kword]['token'])
            # 	if nounmark and kword == nounstart:
            # 		noun_meaning_list = ["---"] if currnoun.meaning ==[] else currnoun.meaning
            # 		noun_meaning = ("#").join(noun_meaning_list)
            # 		UpperSeq.append("(NE<"+str(kword)+">"+noun_meaning)
            # 		nounmark = False
            # 		nounstart = kword
            # 		currnoun = None

            if cmark and kword == cstart:
                UpperSeq.append("(NEC" + str(ccount))
                cmark = False
                cstart = kword

            kword -= 1

        return UpperSeq

    def get_lower_seq(self, kword, endtag, nouns, compound_nouns):
        """
        Generate the lower sequence starting from kword; lower sequence includes only
        words in the VP.

        Note: this function now is used for Petrarch 1 pattern matching only

        """
        LowerSeq = []

        endlist = []
        nounStartEnd = {}  # key is start idx, value is end idx
        for noun in nouns:
            # handle overlapped noun phrases
            # e.g. "A court in Guyana", "Guyana"
            # print(noun.npIDs)
            # print(noun.text)

            if noun.npIDs[0] in nounStartEnd.keys():
                old_range = nounStartEnd[noun.npIDs[0]]['end'] - noun.npIDs[0]
                new_range = noun.npIDs[-1] - noun.npIDs[0]
                if new_range < old_range:
                    continue

            nounStartEnd[noun.npIDs[0]] = {}
            nounStartEnd[noun.npIDs[0]]['end'] = noun.npIDs[-1]
            nounStartEnd[noun.npIDs[0]]['noun'] = noun
            # endlist.append(noun.npIDs[-1])

        compoundStartEnd = {} # key is start idx, value is end idx
        for compound in compound_nouns:
            compoundStartEnd[compound[0]] = compound[1]

        nounmark = False
        nounend = kword
        currnoun = None

        cend = kword
        cmark = False
        ccount = 0

        order = kword
        while kword < endtag:
            if kword in compoundStartEnd.keys() and cmark == False:
                cmark = True
                cend = compoundStartEnd[kword]
                ccount += 1
                LowerSeq.append("(NEC" + str(ccount))
                order += 1


            if kword in nounStartEnd.keys() and nounmark == False:
                nounmark = True
                nounend = nounStartEnd[kword]['end']
                currnoun = nounStartEnd[kword]['noun']

                noun_meaning_list = [
                    "---"] if currnoun.meaning == [] else currnoun.meaning
                noun_meaning = ("#").join(noun_meaning_list)
                LowerSeq.append("(NE<" + str(order) + ">" + noun_meaning)

                # print("kword", kword, "end", nounend)

            LowerSeq.append(self.udgraph.node[kword]['token'].upper())
            if nounmark and kword == nounend:
                LowerSeq.append("~NE")

                nounmark = False
                nounend = kword
                currnoun = None

            if cmark and kword == cend:
                LowerSeq.append("~NEC"+str(ccount))

                cmark = False
                cend = kword
                order += 1


            kword += 1
            order += 1

        return LowerSeq

    def make_event_strings(self, CodedEv, UpperSeq, LowerSeq, SourceLoc, TargetLoc, IsPassive, EventCode, line, verbhead):
        """
        Creates the set of event strings, handing compound actors and symmetric
        events.

        Note: this function now is used for Petrarch 1 pattern matching only

        """

        CodedEvents = CodedEv
        global SentenceLoc
        #global SentenceLoc, SentenceID

        def extract_code_fields(fullcode):
            """ Returns list containing actor code and optional root and text strings """
            if PETRglobals.CodePrimer in fullcode:
                maincode = fullcode[:fullcode.index(PETRglobals.CodePrimer)]
                rootstrg = None
                textstrg = None
                if PETRglobals.WriteActorRoot:
                    part = fullcode.partition(PETRglobals.RootPrimer)
                    if PETRglobals.WriteActorText:
                        rootstrg = part[2].partition(PETRglobals.TextPrimer)[0]
                    else:
                        rootstrg = part[2]
                if PETRglobals.WriteActorText:
                    textstrg = fullcode.partition(PETRglobals.TextPrimer)[2]
                return [maincode, rootstrg, textstrg]

            else:
                return [fullcode, None, None]

        def make_events(codessrc, codestar, codeevt, CodedEvents_, line, verbhead):
            """
            Create events from each combination in the actor lists except self-references
            """
            CodedEvents = CodedEvents_
            global SentenceLoc
            for thissrc in codessrc:
                #if '(NEC' in thissrc:
                #    logger.warning(
                #        '(NEC source code found in make_event_strings(): {}'.format(self.ID))
                #    CodedEvents = []
                #    return
                srclist = extract_code_fields(thissrc)

                if srclist[0][0:3] == '---' and len(SentenceLoc) > 0:
                    # add location if known <14.09.24: this still hasn't been
                    # implemented <>
                    srclist[0] = SentenceLoc + srclist[0][3:]
                for thistar in codestar:
                    #if '(NEC' in thistar:
                    #    logger.warning(
                    #        '(NEC target code found in make_event_strings(): {}'.format(self.ID))
                    #    CodedEvents = []
                    #    return
                    tarlist = extract_code_fields(thistar)
                    # skip self-references based on code
                    if srclist[0] != tarlist[0]:
                        if tarlist[0][0:3] == '---' and len(SentenceLoc) > 0:
                            # add location if known -- see note above
                            tarlist[0] = SentenceLoc + tarlist[0][3:]
                        if IsPassive:
                            templist = srclist
                            srclist = tarlist
                            tarlist = templist
                        # print(srclist[0], tarlist[0], codeevt)
                        CodedEvents.append([srclist[0], tarlist[0], codeevt])
                        if PETRglobals.WriteActorRoot:
                            CodedEvents[-1].extend([srclist[1], tarlist[1]])
                        if PETRglobals.WriteActorText:
                            CodedEvents[-1].extend([srclist[2], tarlist[2]])
                        CodedEvents[-1].append(line)
                        CodedEvents[-1].append(verbhead)

            return CodedEvents

        def expand_compound_codes(codelist):
            """
            Expand coded compounds, that is, codes of the format XXX/YYY
            """
            for ka in range(len(codelist)):
                if '/' in codelist[ka]:
                    parts = codelist[ka].split('/')
                    # this will insert in order, which isn't necessary but might be
                    # helpful
                    kb = len(parts) - 2
                    codelist[ka] = parts[kb + 1]
                    while kb >= 0:
                        codelist.insert(ka, parts[kb])
                        kb -= 1

        logger = logging.getLogger('petr_log')
        try:
            srccodes = self.get_loccodes(
                SourceLoc, CodedEvents, UpperSeq, LowerSeq)
            logger.debug("srccodes: %s", srccodes)
            expand_compound_codes(srccodes)
            tarcodes = self.get_loccodes(
                TargetLoc, CodedEvents, UpperSeq, LowerSeq)
            logger.debug("tarcodes: %s", tarcodes)
            expand_compound_codes(tarcodes)
        except:

            logger.warning(
                'tuple error when attempting to extract src and tar codes in make_event_strings(): {}'.format(self.ID))
            return CodedEvents

        SentenceLoc = ''

        if len(srccodes) == 0 and len(tarcodes) == 0:
            logger.debug(
                'Empty codes in make_event_strings(): {}'.format(self.ID))
            return CodedEvents
        if ':' in EventCode:  # symmetric event
            if srccodes[0] == '---' or tarcodes[0] == '---':
                if tarcodes[0] == '---':
                    tarcodes = srccodes
                else:
                    srccodes = tarcodes
            ecodes = EventCode.partition(':')
            CodedEvents = make_events(srccodes, tarcodes, ecodes[
                                      0], CodedEvents, line, verbhead)
            CodedEvents = make_events(tarcodes, srccodes, ecodes[
                                      2], CodedEvents, line, verbhead)
        else:
            CodedEvents = make_events(
                srccodes, tarcodes, EventCode, CodedEvents, line, verbhead)

        if PETRglobals.RequireDyad:
            ka = 0
            # need to evaluate the bound every time through the loop
            while ka < len(CodedEvents):
                if CodedEvents[ka][0] == '---' or CodedEvents[ka][1] == '---':
                    del CodedEvents[ka]
                else:
                    ka += 1

        # print(PETRglobals.RequireDyad)
        # print(CodedEvents)
        # raw_input()

        if not CodedEvents or len(CodedEvents) == 0:
            return CodedEvents

        # remove duplicates
        ka = 0
        # need to evaluate the bound every time through the loop
        while ka < len(CodedEvents) - 1:
            kb = ka + 1
            while kb < len(CodedEvents):
                if CodedEvents[ka] == CodedEvents[kb]:
                    del CodedEvents[kb]
                else:
                    kb += 1
            ka += 1

        return CodedEvents

    def get_loccodes(self, thisloc, CodedEvents, UpperSeq, LowerSeq):
        """
        Returns the list of codes from a compound, or just a single code if not compound

        Extracting noun phrases which are not in the dictionary: If no actor or agent
        generating a non-null code can be found using the source/target rules, PETRARCH can
        output the noun phrase in double-quotes. This is controlled by the configuration file
        option new_actor_length, which is set to an integer which gives the maximum length
        for new actor phrases extracted. If this is set to zero [default], no extraction is
        done and the behavior is the same as TABARI. Setting this to a large number will
        extract anything found in a (NP noun phrase, though usually true actors contain a
        small number of words. These phrases can then be processed with named-entity-resolution
        software to extend the dictionaries.

            Note: this function now is used for Petrarch 1 pattern matching only
        """

        def get_ne_text(neloc, isupperseq):
            """ Returns the text of the phrase from UpperSeq/LowerSeq starting at neloc. """
            if isupperseq:
                acphr = UpperSeq[neloc - 1]
                ka = neloc - 2  # UpperSeq is stored in reverse order
                # we can get an unbalanced sequence when multi-word verbs cut into
                # the noun phrase: see DEMO-30 in unit-tests
                while ka >= 0 and UpperSeq[ka][0] != '~':
                    acphr += ' ' + UpperSeq[ka]
                    ka -= 1
            else:
                acphr = LowerSeq[neloc + 1]
                ka = neloc + 2
                while LowerSeq[ka][0] != '~':
                    acphr += ' ' + LowerSeq[ka]
                    ka += 1

            return acphr

        def add_code(neloc, isupperseq, cl):
            """
            Appends the code or phrase from UpperSeq/LowerSeq starting at neloc.
            isupperseq determines the choice of sequence

            If PETRglobals.WriteActorText is True, root phrase is added to the code following the
            string PETRglobals.TextPrimer
            """
            codelist = cl

            if isupperseq:
                # "add_code neitem"; nothing to do with acne...
                acneitem = UpperSeq[neloc]
            else:
                acneitem = LowerSeq[neloc]
            accode = acneitem[acneitem.find('>') + 1:]
            if accode != '---':
                codelist.append(accode)
            elif PETRglobals.NewActorLength > 0:  # get the phrase
                acphr = '"' + get_ne_text(neloc, isupperseq) + '"'
                if acphr.count(' ') < PETRglobals.NewActorLength:
                    codelist.append(acphr)
                else:
                    codelist.append(accode)
                if PETRglobals.WriteActorRoot:
                    codelist[-1] += PETRglobals.RootPrimer + '---'

            if PETRglobals.WriteActorText and len(codelist) > 0:
                codelist[-1] += PETRglobals.TextPrimer + \
                    get_ne_text(neloc, isupperseq)

            return codelist

        codelist = []
        if thisloc[1]:

            try:
                neitem = UpperSeq[thisloc[0]]
            except IndexError:

                raise_ParseList_error(
                    'Initial index error on UpperSeq in get_loccodes()')

            # extract the compound codes from the (NEC ... ~NEC sequence
            if '(NEC' in neitem:
                ka = thisloc[0] - 1  # UpperSeq is stored in reverse order
                while '~NEC' not in UpperSeq[ka]:
                    if '(NE' in UpperSeq[ka]:
                        codelist = add_code(ka, True, codelist)
                    ka -= 1
                    if ka < 0:
                        raise_ParseList_error(
                            'Bounds underflow on UpperSeq in get_loccodes()')
            else:
                codelist = add_code(thisloc[0], True, codelist)  # simple code
        else:

            try:
                neitem = LowerSeq[thisloc[0]]
            except IndexError:
                raise_ParseList_error(
                    'Initial index error on LowerSeq in get_loccodes()')
            if '(NEC' in neitem:  # extract the compound codes
                ka = thisloc[0] + 1
                while '~NEC' not in LowerSeq[ka]:
                    if '(NE' in LowerSeq[ka]:
                        add_code(ka, False, codelist)

                    ka += 1
                    if ka >= len(LowerSeq):
                        raise_ParseList_error(
                            'Bounds overflow on LowerSeq in get_loccodes()')
            else:
                codelist = add_code(thisloc[0], False, codelist)  # simple code
        if len(codelist) == 0:  # this can occur if all codes in an (NEC are null
            codelist = ['---']

        return codelist

    def get_events_from_petrarch1_patterns(self):
        """
        checks whether any of petrarch1 patterns match, 
        then fills in the source and target if there has been a
        match. Stores events using make_event_strings().

        Note: the "upper" sequence is the part before the verb and the 
        "lower" sequence is the part after the verb.
        """

        def raise_CheckVerbs_error(kloc, call_location_string):
            """
            Handle problems found at some point internal to check_verbs: skip the verb that
            caused the problem but do [not?] skip the sentence. Logs the error and information on the
            verb phrase and raises CheckVerbsError.
            This is currently only used for check_passive()
            15.04.29: pas -- is that supposed to be "not"?
            """
            #global SentenceID
            warningstr = call_location_string + \
                'in check_verbs; verb sequence {} skipped: {}'.format(self.udgraph.node[kloc]['lemma'],
                                                                      self.ID)
            logger = logging.getLogger('petr_log')
            logger.warning(warningstr)
            raise CheckVerbsError

        logger = logging.getLogger("petr_log.petrarch1")
        nouns, compound_nouns = self.get_all_nounPhrases()
        # raw_input()

        CodedEvents = []
        SourceLoc = ""

        head_verbs = self.get_rootNode()

        other_verbs = []
        for node in self.udgraph.nodes(data=True):
            nodeID = node[0]
            attrs = node[1]

            if nodeID in head_verbs:
                continue

            if 'pos' in attrs and attrs['pos'] == 'VERB':
                other_verbs.append(nodeID)
        other_verbs.sort()

        verbs = [] #order the head verbs first and then other verbs.  
        verbs.extend(head_verbs)
        verbs.extend(other_verbs)

        for verbID in verbs:
            attrs = self.udgraph.node[verbID]
            
            if 'pos' in attrs and attrs['pos'] == 'VERB':

                verb = self.get_verbPhrase(verbID)
                verbhead = verb.head.upper()
                logger.debug("CV-0: %s  %s", verb.text,
                             verbhead in PETRglobals.P1VerbDict['verbs'])
                # raw_input()
                IsPassive = False
                for successor in self.udgraph.successors(verbID):
                    if 'relation' in self.udgraph[verbID][successor] and self.udgraph[verbID][successor]['relation'] in ['auxpass']:
                        IsPassive = True
                        break
                # raw_input(IsPassive)

                '''Find verb code from verb dictionary'''
                if verbhead in PETRglobals.P1VerbDict['verbs']:
                    logger.debug("CV-1 Found: %s", verb.text)
                    patternlist = PETRglobals.P1VerbDict['verbs'][verbhead]

                    SourceLoc = ""
                    TargetLoc = ""

                    hasmatch = False

                    verbcode = '---'
                    meaning = ''
                    verbdata = {}

                    verb_start = verb.headID
                    verb_end = verb.headID

                    if not patternlist.keys() == ['#']:
                        # compound verb, look ahead
                        # e.g. +MEET_WITH
                        i = verb.headID + 1
                        found_flag = True
                        while found_flag:
                            word = self.udgraph.node[i]['lemma'].upper()
                            if word in patternlist:
                                if '#' in patternlist[word]:
                                    found_flag = False
                                    verb_end = i
                                    upper_compound = patternlist[word]['#']
                                    hasmatch = True
                                    if not '#' in upper_compound:
                                        raise_CheckVerbs_error(
                                            i, "find verb code")

                                    verbdata = upper_compound['#']
                                else:
                                    i += 1
                            else:
                                if '#' in patternlist:
                                    verbdata = patternlist['#']['#']
                                else:
                                    # No match found on the verb.
                                    raise_CheckVerbs_error(i, "find verb code")
                                break

                    if not hasmatch:
                        if not patternlist['#'].keys() == ['#']:
                            # Compound verb, look behind
                            #e.g. RE_ADMIT
                            i = verb.headID - 1
                            found_flag = True
                            while found_flag and i >= 0:
                                word = self.udgraph.node[i]['lemma'].upper()
                                if word in patternlist['#']:
                                    if '#' in patternlist['#'][word]:
                                        found_flag = False
                                        verb_start = i
                                        verbdata = patternlist['#'][word]['#']
                                        hasmatch = True
                                    else:
                                        i -= 1
                                else:

                                    if '#' in patternlist:
                                        verbdata = patternlist['#']['#']
                                    break

                        if not hasmatch:
                            # Simple verb
                            if '#' in patternlist['#']:
                                verbdata = patternlist['#']['#']
                                hasmatch = True

                    if not verbdata == {}:
                        meaning = verbdata['meaning']
                        verbcode = verbdata['code']
                        line = verbdata['line']
                        logger.debug(
                            "CV-1 Verb Code Found:\n meaning:%s \n verbcode: %s \n line: %s", meaning, verbcode, line)

                    # Find code from pattern dictionary
                    upper = self.get_upper_seq(verb_start - 1, nouns, compound_nouns)
                    logger.debug("Upper sequence: %s", upper)
                    lower = self.get_lower_seq(
                        verb_end + 1, len(self.udgraph.node), nouns, compound_nouns)
                    logger.debug("Lower sequence: %s", lower)
                    # raw_input()

                    if not meaning == '':
                        patternlist = PETRglobals.P1VerbDict[
                            'phrases'][meaning]
                    # logger.debug("CV-2 patlist: %s", patternlist.keys())

                    vpm, lowsrc, lowtar = self.petrarch1_verb_pattern_match(
                        patternlist, upper, lower)
                    hasmatch = False
                    if not vpm == {}:
                        hasmatch = True
                        EventCode = vpm[0]['code']
                        line = vpm[0]['line']
                        SourceLoc = lowsrc if not lowsrc == "" else vpm[2]
                        TargetLoc = lowtar if not lowtar == "" else vpm[1]

                        logger.debug("EventCode: %s,%s,%s,%s",
                                     EventCode, line, SourceLoc, TargetLoc)
                    # raw_input()

                    if hasmatch and EventCode == '---':
                        hasmatch = False
                    if not hasmatch and verbcode != '---':
                        logger.debug(
                            "Matched on the primary verb %s, %s, %s", verbhead, meaning, line)
                        EventCode = verbcode
                        hasmatch = True

                    if hasmatch:
                        if TargetLoc == "":
                            TargetLoc = self.find_target(lower, TargetLoc)
                            logger.debug("CV-3 trg %s", TargetLoc)

                        # print("TargetLoc", TargetLoc)
                        if not TargetLoc == "":
                            if SourceLoc == "":
                                # print(upper)
                                # print(lower)
                                # print(TargetLoc == "")
                                if not TargetLoc[0] == "":
                                    SourceLoc = self.find_source(
                                        upper, lower, SourceLoc, TargetLoc)
                            if not SourceLoc == "":
                                logger.debug("CV-3 src %s", SourceLoc)
                                CodedEvents = self.make_event_strings(
                                    CodedEvents, upper, lower, SourceLoc, TargetLoc, IsPassive, EventCode, line, verbhead)

                                logger.debug("coded_events: %s", CodedEvents)
                                logger.debug("line: %s", line)
                                # for event in CodedEvents:
                                # event.append(line)
            if verbID not in head_verbs and CodedEvents and '---' not in [item for event in CodedEvents for item in event]:
                break

        # return CodedEvents,SourceLoc
        return CodedEvents

    def skip_item(self, item):
        """ 
        Determines whether a particular item in the parse needs to be skipped 

        Note: this function now is used for Petrarch 1 pattern matching only

        """
        if item[0] in "~(":
            return 1
        if item in ["THE", "A", "AN", "IT", "HE", "THEY",
                                "HER", "HAS", "HAD", "HAVE", "SOME", "FEW", "THAT"]:
            return 2
        if item in ["HUNDRED", "THOUSAND", "MILLION", "BILLION", "TRILLION", "DOZEN",
                    "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE"]:
            return 3
        if item in ["DOLLAR", "DUCAT"]:
            return 5
        try:
            int(item)
            return 4
        except:
            return 0

    def petrarch1_verb_pattern_match(self, patlist, upper, lower):
        """
        ##########################################
        ##
        ##      Symbols:
        ##          $ = Source
        ##          + = Target
        ##          ^ ="Skip to end of the (NE
        ##          % = Compound
        ##
        ##      I'm sorry this is so long, but upper and lower matches are just different
        ##      enough where this actually makes sense
        ##
        ##########################################

        Note: this function now is used for Petrarch 1 pattern matching only

        """

        logger = logging.getLogger("petr_log.petrarch1")

        def find_actor(phrase, i):
            for j in range(i, len(phrase)):
                if phrase[j][0] == "(":
                    return j
            #logger.debug("NO ACTOR FOUND: %s, %i", phrase,j)
            return i

        def upper_match(pathdict):

            ########################
            # Match upper phrase
            ########################

            phrase = upper
            path = pathdict

            option = 0
            matchlist = []
            pathleft = [(pathdict, 0, 0)]  # 3-tuples (path,index,option)

            in_NE = False  # if in noun phrase
            in_NEC = False  # if in compound noun phrase

            source = ""
            target = ""

            # logger.debug("\nChecking upper %s, %s", phrase,path.keys())

            i = 0
            while i < len(phrase):
                # print(i)
                # logger.debug("Checking  %s, %s", phrase[i],path.keys())

                skipcheck = self.skip_item(phrase[i])

                # check direct word match
                if phrase[i] in path and not option > 0:
                    # logger.debug("upper matched a word %s", phrase[i])

                    matchlist.append(phrase[i])
                    pathleft.append((path, i, 1))
                    path = path[phrase[i]]

                # maybe a synset match
                elif 'synsets' in path and not option > 1:
                    # logger.debug("could be a synset")
                    matchflag = False
                    for synset in path['synsets'].keys():
                        if phrase[i] in PETRglobals.P1VerbDict['verbs'][synset]:
                            # logger.debug("found a synset match")

                            matchlist.append(synset)
                            pathleft.append((path, i, 2))
                            path = path['synsets'][synset]

                            i += 1
                            matchflag = True
                            break

                    option = 0 if matchflag else 2
                    continue

                # check for target match
                elif in_NE and (not option > 2) and '+' in path:
                    # i == end of noun phrase
                    pathleft.append((path, i, 3, target))

                    i = find_actor(phrase, i)
                    # update i from the end of noun phrase to start of noun
                    # phrase
                    target = [i, True]  # i == start of noun phrase

                    matchlist += ['+']
                    path = path['+']

                    # logger.debug("Matching phrase target %s", target)
                    continue

                # check for source match
                elif in_NE and (not option > 3) and '$' in path:
                    # i == end of noun phrase
                    pathleft.append((path, i, 4, source))

                    i = find_actor(phrase, i)
                    # update i from the end of noun phrase to start of noun
                    # phrase
                    source = [i, True]  # i == start of noun phrase

                    matchlist.append(source)
                    path = path['$']

                    # logger.debug("Matching phrase source %s", source)
                    continue

                # check for phrase skip
                elif in_NE and (not option > 4) and '^' in path:
                    j = i
                    # logger.debug("Matching phrase skip")

                    matchlist.append('^')
                    while j >= 0:
                        if "~NE" == phrase[j]:
                            pathleft.append((path, i, 5))
                            path = path['^']
                            i = j - 1
                            break
                        j -= 1

                    if j >= 0:
                        continue

                # check for compound phrase
                elif (not in_NE) and in_NEC and (not option > 5) and '%' in path:
                    logger.debug("Matching compound %s %i", phrase, i)
                    ka = i

                    while '(NEC' not in phrase[ka]:
                        ka += 1
                        if ka >= len(phrase):
                            option = 6
                            break
                    if option == 6:
                        continue

                    source = [ka, True]
                    target = source
                    pathleft.append((path, i, 6))
                    path = path['%']
                    matchlist.append('%')
                    i = ka
                    continue

                if skipcheck > 0:
                    # logger.debug("skipping: %i skipcheck: %i",i,skipcheck)
                    if '~NEC' in phrase[i]:
                        in_NEC = not in_NEC
                    elif '~NE' in phrase[i]:
                        in_NE = not in_NE

                    if i < len(lower) - 1:  # ?? why
                        i += 1
                        continue

                    if not '#' in path:
                        return False, {}
                    logger.debug("Upper pattern matched at end %s", matchlist)
                    return True, (path['#'], target, source)

                if (not i >= len(upper)) and not option > 6:
                    i += 1
                    pathleft.append((path, i, 7))
                    # logger.debug("Skipping")
                    option = 0
                    matchlist.append("*")
                    continue

                elif "#" in path:
                    logger.debug("Upper pattern matched: %s", matchlist)
                    return True, (path['#'], target, source)

                # return to last point of departure
                elif not pathleft[-1][2] == 0:
                    # logger.debug("retracing: %s, %s, %s", pharse[i], path, pharse[i] in path)
                    p = pathleft.pop()
                    path = p[0]
                    i = p[i] + 1
                    option = p[2]
                    if option == 3:
                        target = p[3]
                    elif option == 4:
                        source = p[3]
                    matchlist.pop()
                    continue

                else:
                    # logger.debug("no match in upper: %s",
                    #              pathleft[-1][0].keys())
                    return False, {}

                i += 1
                option = 0
                logger.debug("MATCHED: %s, %s", matchlist, path.keys())

            if "#" in path:
                return True, (path['#'], target, source)

            # logger.debug("NO MATCH IN UPPER")
            return False, {}

        #################################################
        # Match lower phrase via Depth-First-ish Search
        #################################################

        # Stack is of 3-tuples (path,index,option)
        path = patlist
        phrase_return = True

        option = 0
        matchlist = []
        phrase_actors = {}
        pathleft = [(path, 0, 0)]  # 3-tuples (path,index,option)

        in_NE = False  # if in noun phrase
        in_NEC = False  # if in compound noun phrase

        source = ""
        target = ""

        i = 0

        logger.debug('\nChecking phrase %s', lower)
        phrase_actor = ""
        while i < len(lower):
            if pathleft == []:
                pathleft = [(path, i, 0)]
                #logger.debug('checking %s, option: %i,phrase_actor: %s, %s,%s', lower[i],option,phrase_actor,in_NE,path.keys())

            skipcheck = self.skip_item(lower[i])

            # return to last point of departure

            if skipcheck > 0 and option > -1:
                # logger.debug("Skipping")
                if 'NEC' in lower[i]:
                    in_NEC = not in_NEC
                elif 'NE' in lower[i]:
                    in_NE = not in_NE
                    if len(lower[i]) > 3:
                        phrase_actor = i
                        phrase_actors[i] = i

                if i < len(lower) - 1:
                    i += 1
                    continue
                if '#' in path:
                    option = 7

            elif i == len(lower) - 1 and not pathleft[-1][2] == 0:
                # logger.debug("retracing "+str(len(pathleft)))
                p = pathleft.pop()
                path = p[0]
                i = p[1] + 1
                option = p[2]
                matchlist.pop()
                phrase_actors[i] = phrase_actors.setdefault(i, phrase_actor)
                continue

            phrase_actors[i] = phrase_actors.setdefault(i, phrase_actor)
            # print(phrase_actors)

            # check direct word match
            if lower[i] in path and not option > 0:
                # logger.debug("lower matched a word %s", lower[i])

                matchlist.append(lower[i])
                pathleft.append((path, i, 1))
                path = path[lower[i]]

            # maybe a synset match
            elif 'synsets' in path and not option > 1:
                # logger.debug("could be a synset")
                matchflag = False
                for synset in path['synsets'].keys():
                    if lower[i] in PETRglobals.P1VerbDict['verbs'][synset]:
                        # logger.debug("found a synset match")

                        matchlist.append(synset)
                        pathleft.append((path, i, 2))
                        path = path['synsets'][synset]

                        i += 1
                        matchflag = True
                        break

                option = 0 if matchflag else 2
                continue

            # check for target match
            elif in_NE and (not option > 2) and '+' in path:
                pathleft.append((path, i, 3, target))

                target = [phrase_actors[i], False]

                matchlist += [target]
                path = path['+']

                logger.debug("Matching phrase target %s", target)
                continue

            # check for source match
            elif in_NE and (not option > 3) and '$' in path:
                pathleft.append((path, i, 4, source))

                source = [phrase_actors[i], False]  # i == start of noun phrase

                matchlist.append(source)
                path = path['$']

                # logger.debug("Matching phrase source %s", source)
                continue

            # check for phrase skip
            elif in_NE and (not option > 4) and '^' in path:
                j = i
                # logger.debug("Matching phrase skip")

                matchlist.append('^')
                while j < len(lower):
                    if "~NE" == lower[j]:
                        pathleft.append((path, i, 5))
                        path = path['^']
                        i = j + 1

                        in_NE = False
                        break
                    j += 1

                if not j < len(lower):
                    i += 1
                continue

            elif not in_NE and in_NEC and (not option > 5) and '%' in path:
                # in original code is "upper" why?
                logger.debug("Matching compound %s %i", lower, i)

                ka = i

                while '(NEC' not in lower[ka]:
                    ka += 1
                    if ka >= len(lower):
                        option = 6
                        break

                if option == 6:
                    continue
                source = lower[ka][-3:]
                target = source
                pathleft.append((path, i, 6))
                path = path['%']
                matchlist.append('%')
                continue

            elif i + 1 < len(lower) and not option > 6:
                # logger.debug("skipping")
                option = 0
                pathleft.append((path, i, 7))
                i += 1
                matchlist.append("*")
                continue

            elif '#' in path:
                logger.debug("Lower pattern matched %s", matchlist)

                result, data = upper_match(path['#'])
                if result:
                    return data, source, target

                # logger.debug("retracing "+str(len(pathleft)))
                p = pathleft.pop()
                path = p[0]
                i = p[1] + 1
                option = p[2]
                if option == 3:
                    target = p[3]
                elif option == 4:
                    source = p[3]

                if not matchlist == []:
                    m = matchlist.pop()
                    if m == '$':
                        source = ""
                continue

            elif not pathleft[-1][2] == 0:
                # logger.debug("retracing "+str(len(pathleft)))
                p = pathleft.pop()
                path = p[0]
                i = p[1] + 1
                option = p[2]
                if option == 3:
                    target = p[3]
                elif option == 4:
                    source = p[3]
                matchlist.pop()
                continue

            else:
                # logger.debug("no match in lower %s", pathleft.keys())
                phrase_return = False
                break

            i += 1
            option = 0

        return {}, "", ""

    def find_target(self, LowerSeq, TargetLoc):
        """
        Assigns TargetLoc

        Priorities for assigning target:
            1. first coded (NE in LowerSeq that does not have the same code as
            SourceLoc; codes are not checked with either SourceLoc or the
            candidate target are compounds (NEC
            2. first null-coded (NE in LowerSeq ;
            3. first coded (NE in UpperSeq -- that is, searching backwards from
            the verb -- that does not have the same code as SourceLoc;
            4. first null-coded (NE in UpperSeq

        Note: this function now is used for Petrarch 1 pattern matching only

        """

        # Look in the lower phrase after the verb
        k = 0
        for item in LowerSeq:
            if item.startswith('(NEC'):
                return [k, False]
            if item.startswith('(NE') and not item.endswith('>---'):
                return [k, False]
            k += 1

        k = 0
        for item in LowerSeq:
            if item.startswith('(NE'):
                return [k, False]
            k += 1

        return TargetLoc

    def find_source(self, UpperSeq, LowerSeq, Src, Trg):
        """
        Assign SourceLoc to the first coded or compound (NE in the UpperSeq; if
        neither found then first (NE with --- code Note that we are going through
        the sentence in normal order, so we go through UpperSeq in reverse order.
        Also note that this matches either (NE and (NEC: these are processed
        differently in make_event_string()

        Note: this function now is used for Petrarch 1 pattern matching only

        """
        SourceLoc = Src
        kseq = 0
        # print(LowerSeq[Trg[0]])
        while kseq < len(UpperSeq):
            if ('(NEC' in UpperSeq[kseq]): # and not UpperSeq[kseq].endswith(LowerSeq[Trg[0]].split('>')[1]):
                SourceLoc = [kseq, True]
                return SourceLoc

            if ('(NE' in UpperSeq[kseq]) and ('>---' not in UpperSeq[kseq]): #and not UpperSeq[kseq].endswith(LowerSeq[Trg[0]].split('>')[1]):

                SourceLoc = [kseq, True]
                return SourceLoc
            kseq += 1
        kseq = 0
        while kseq < len(UpperSeq):
            if ('(NE' in UpperSeq[kseq]): # and not UpperSeq[kseq].endswith(LowerSeq[Trg[0]].split('>')[1]):
                SourceLoc = [kseq, True]
                return SourceLoc
            kseq += 1
        return SourceLoc

    def get_all_nounPhrases(self):
        """
        extract all noun phrases in the sentence and their codes

        Note: this function now is used for Petrarch 1 pattern matching only

        """
        logger = logging.getLogger("petr_log.petrarch1")
        nouns = []
        compound_nouns = []

        for node in self.udgraph.nodes(data=True):
            nodeID = node[0]
            attrs = node[1]

            if 'pos' in attrs and attrs['pos'] in ['NOUN', 'PROPN']:

                found = False
                predecessors = self.udgraph.predecessors(nodeID)
                for predecessor in predecessors:
                    if 'relation' in self.udgraph[predecessor][nodeID] and self.udgraph[predecessor][nodeID]['relation'] in ['nsubj', 'obj', 'nmod', 'dobj', 'iobj', 'nsubjpass']:
                        found = True
                        break

                if found:
                    noun = self.get_nounPharse(nodeID)
                    nouns.append(noun)

                    conj_nouns = self.get_conj_noun_for_petrarch1(nodeID, noun)
                    nouns.extend(conj_nouns)

                    if conj_nouns:
                        ids = []
                        ids.extend(noun.npIDs)
                        for conj in conj_nouns:
                            ids.extend(conj.npIDs)
                        ids.sort()
                        compound_nouns.append((ids[0], ids[-1])) #start_idx and end_idx of compound noun phrase
                        print("compound:", (ids[0], ids[-1]))

        
        for noun in nouns:
            noun.get_meaning()
            noun.meaning = ["---"] if noun.meaning == [] else noun.meaning
            logger.debug("noun: " + noun.head + " code: " +
                                 (("#").join(noun.meaning) if noun.meaning != None else '-'))

        return nouns, compound_nouns

    def get_conj_noun_for_petrarch1(self, nodeID, noun):
        """ method for extracting other conjunt nouns of this noun
            for example: Brazil and the United States, 
            Given the nodeID of Brazil, it will return noun phrase object of "the United States"

            apply modifiers to each conjunt nouns
            e.g. "Lawmakers and officials in Arnor"
            two noun phrases will be generated: lawmakers in Arnor, officials in Arnor

            Note: this function now is used for Petrarch 1 pattern matching only

        """
        conj_noun = []
        for successor in self.udgraph.successors(nodeID):
            if(self.udgraph[nodeID][successor]['relation'] == 'conj'):
                # conj_noun.append(self.get_nounPharse(successor))
                conjnouns = self.get_nounPharse(successor)

                for conjnoun in [conjnouns]:
                    conjnoun.prep_phrase.extend(noun.prep_phrase)
                    for prep in conjnoun.prep_phrase:
                        conjnoun.npIDs.extend(prep.ppIDs)

                    tempprepset = set(conjnoun.prep_phrase)
                    conjnoun.prep_phrase = list(tempprepset)

                    tempIDset = set(conjnoun.npIDs)
                    conjnoun.npIDs = list(tempIDset)
                    conjnoun.npIDs.sort()
                    # print(conjnoun.prep_phrase)
                    npTokens = []
                    for npID in conjnoun.npIDs:
                        npTokens.append(
                            self.udgraph.node[npID]['token'])

                    nntext = (' ').join(npTokens)
                    conjnoun.text = nntext

                conj_noun.extend([conjnouns])

        return conj_noun
