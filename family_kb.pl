% =========================================================
% FAMILY KNOWLEDGE BASE - PYTHOLOG COMPATIBLE
% =========================================================
% ASSIGNMENT 2: All hardcoded facts have been removed.
% Facts are acquired dynamically through the AIML collection
% interface (collect.aiml) and appended below by fact_builder.py
%
% To add family members, type:  add person
% in the chatbot console or Streamlit UI.
% =========================================================


% =========================================================
% BASIC RELATION RULES
% =========================================================

father(X, Y) :- male(X), parent(X, Y).
mother(X, Y) :- female(X), parent(X, Y).
son(X, Y) :- male(X), parent(Y, X).
daughter(X, Y) :- female(X), parent(Y, X).
child(X, Y) :- parent(Y, X).
husband(X, Y) :- married(X, Y).
wife(X, Y) :- married(Y, X).

% =========================================================
% SIBLING RULES
% =========================================================

sibling(X, Y) :- parent(Z, X), parent(Z, Y), different(X, Y).
brother(X, Y) :- sibling(X, Y), male(X).
sister(X, Y) :- sibling(X, Y), female(X).

% =========================================================
% GRANDPARENT RULES
% =========================================================

grandparent(X, Y) :- parent(X, Z), parent(Z, Y).
grandfather(X, Y) :- father(X, Z), parent(Z, Y).
grandmother(X, Y) :- mother(X, Z), parent(Z, Y).
grandchild(X, Y) :- grandparent(Y, X).
grandson(X, Y) :- grandchild(X, Y), male(X).
granddaughter(X, Y) :- grandchild(X, Y), female(X).

% =========================================================
% DADA / DADI / NANA / NANI
% =========================================================

dada(X, Y) :- father(F, Y), father(X, F).
dadi(X, Y) :- father(F, Y), mother(X, F).
nana(X, Y) :- mother(M, Y), father(X, M).
nani(X, Y) :- mother(M, Y), mother(X, M).

% =========================================================
% EXTENDED FAMILY RULES
% =========================================================

uncle(X, Y) :- brother(X, Z), parent(Z, Y).
aunt(X, Y) :- sister(X, Z), parent(Z, Y).
cousin(X, Y) :- parent(A, X), parent(B, Y), sibling(A, B), different(X, Y).
nephew(X, Y) :- male(X), sibling(Z, Y), parent(Z, X).
niece(X, Y) :- female(X), sibling(Z, Y), parent(Z, X).

% =========================================================
% EASTERN / URDU RELATION RULES
% =========================================================

chacha(X, Y) :- father(F, Y), brother(X, F).
phoophi(X, Y) :- father(F, Y), sister(X, F).
maamu(X, Y) :- mother(M, Y), brother(X, M).
khala(X, Y) :- mother(M, Y), sister(X, M).
chachi(X, Y) :- chacha(C, Y), married(C, X).
phuppa(X, Y) :- phoophi(P, Y), married(X, P).
maami(X, Y) :- maamu(M, Y), married(M, X).
khalu(X, Y) :- khala(K, Y), married(X, K).

% =========================================================
% IN-LAW RULES (split - no semicolons for pytholog)
% =========================================================

father_in_law(X, Y) :- married(Y, S), father(X, S).
father_in_law(X, Y) :- married(S, Y), father(X, S).
mother_in_law(X, Y) :- married(Y, S), mother(X, S).
mother_in_law(X, Y) :- married(S, Y), mother(X, S).
brother_in_law(X, Y) :- married(Y, S), brother(X, S).
brother_in_law(X, Y) :- married(S, Y), brother(X, S).
sister_in_law(X, Y) :- married(Y, S), sister(X, S).
sister_in_law(X, Y) :- married(S, Y), sister(X, S).
son_in_law(X, Y) :- daughter(D, Y), married(X, D).
son_in_law(X, Y) :- daughter(D, Y), married(D, X).
daughter_in_law(X, Y) :- son(S, Y), married(S, X).
daughter_in_law(X, Y) :- son(S, Y), married(X, S).

% =========================================================
% ANCESTOR / DESCENDANT RECURSION
% =========================================================

ancestor(X, Y) :- parent(X, Y).
ancestor(X, Y) :- parent(X, Z), ancestor(Z, Y).
descendant(X, Y) :- ancestor(Y, X).

% =========================================================
% SAME CITY / OCCUPATION / GENERATION
% =========================================================

same_city(X, Y) :- lives_in(X, C), lives_in(Y, C), different(X, Y).
same_occupation(X, Y) :- occupation(X, O), occupation(Y, O), different(X, Y).
same_generation(X, Y) :- grandparent(G, X), grandparent(G, Y), different(X, Y).
same_generation(X, Y) :- parent(P, X), parent(P, Y), different(X, Y).

% =========================================================
% BLOOD RELATIVE / FAMILY MEMBER
% =========================================================

blood_relative(X, Y) :- ancestor(X, Y).
blood_relative(X, Y) :- ancestor(Y, X).
blood_relative(X, Y) :- sibling(X, Y).
blood_relative(X, Y) :- cousin(X, Y).
blood_relative(X, Y) :- ancestor(Z, X), ancestor(Z, Y), different(X, Y).
family_member(X, Y) :- parent(X, Y).
family_member(X, Y) :- parent(Y, X).
family_member(X, Y) :- sibling(X, Y).

% =========================================================
% SPOUSE
% =========================================================

spouse(X, Y) :- married(X, Y).
spouse(X, Y) :- married(Y, X).

% =========================================================
% DYNAMICALLY ADDED FACTS APPEAR BELOW THIS LINE
% =========================================================
% === Dynamically added fact ===
male(ali).
parent(akbar, ali).
parent(nadiya, ali).
dob(ali, d2003_04_25).
lives_in(ali, kasur).
occupation(ali, student).
religion(ali, muslism).
married(ali, ayesha).

% === Dynamically added fact ===
male(alia).
parent(male, alia).
parent(female, alia).
dob(alia, d1990_08_09).
occupation(alia, berozgar).
religion(alia, muslim).
married(alia, mudassar).
different(alia, ali).
different(ali, alia).
