import sys

# deep nesting: the CPython-hosted compiler stopped at about 70 nested brackets with RecursionError.
# 200 brackets and 99 indentation levels are CPython's own limits; tests/errors/nest_*.py go past
# them and past Pystachy's 5,000 levels (longer chains here would slow the GC-stress stage down)
a = 1
x = ((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((((1))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))))
print(x)
l = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]
print(len(l))
x = 1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1+1
print(x)
x = ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------1
print(x)
x = 1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1**1
print(x)
b = not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not not a
print(b)
x = a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a if a else a
print(x)
y = 1
if y == 0:
    print(0)
elif y == 1:
    print(1)
elif y == 2:
    print(2)
elif y == 3:
    print(3)
elif y == 4:
    print(4)
elif y == 5:
    print(5)
elif y == 6:
    print(6)
elif y == 7:
    print(7)
elif y == 8:
    print(8)
elif y == 9:
    print(9)
elif y == 10:
    print(10)
elif y == 11:
    print(11)
elif y == 12:
    print(12)
elif y == 13:
    print(13)
elif y == 14:
    print(14)
elif y == 15:
    print(15)
elif y == 16:
    print(16)
elif y == 17:
    print(17)
elif y == 18:
    print(18)
elif y == 19:
    print(19)
elif y == 20:
    print(20)
elif y == 21:
    print(21)
elif y == 22:
    print(22)
elif y == 23:
    print(23)
elif y == 24:
    print(24)
elif y == 25:
    print(25)
elif y == 26:
    print(26)
elif y == 27:
    print(27)
elif y == 28:
    print(28)
elif y == 29:
    print(29)
elif y == 30:
    print(30)
elif y == 31:
    print(31)
elif y == 32:
    print(32)
elif y == 33:
    print(33)
elif y == 34:
    print(34)
elif y == 35:
    print(35)
elif y == 36:
    print(36)
elif y == 37:
    print(37)
elif y == 38:
    print(38)
elif y == 39:
    print(39)
elif y == 40:
    print(40)
elif y == 41:
    print(41)
elif y == 42:
    print(42)
elif y == 43:
    print(43)
elif y == 44:
    print(44)
elif y == 45:
    print(45)
elif y == 46:
    print(46)
elif y == 47:
    print(47)
elif y == 48:
    print(48)
elif y == 49:
    print(49)
elif y == 50:
    print(50)
elif y == 51:
    print(51)
elif y == 52:
    print(52)
elif y == 53:
    print(53)
elif y == 54:
    print(54)
elif y == 55:
    print(55)
elif y == 56:
    print(56)
elif y == 57:
    print(57)
elif y == 58:
    print(58)
elif y == 59:
    print(59)
elif y == 60:
    print(60)
elif y == 61:
    print(61)
elif y == 62:
    print(62)
elif y == 63:
    print(63)
elif y == 64:
    print(64)
elif y == 65:
    print(65)
elif y == 66:
    print(66)
elif y == 67:
    print(67)
elif y == 68:
    print(68)
elif y == 69:
    print(69)
elif y == 70:
    print(70)
elif y == 71:
    print(71)
elif y == 72:
    print(72)
elif y == 73:
    print(73)
elif y == 74:
    print(74)
elif y == 75:
    print(75)
elif y == 76:
    print(76)
elif y == 77:
    print(77)
elif y == 78:
    print(78)
elif y == 79:
    print(79)
elif y == 80:
    print(80)
elif y == 81:
    print(81)
elif y == 82:
    print(82)
elif y == 83:
    print(83)
elif y == 84:
    print(84)
elif y == 85:
    print(85)
elif y == 86:
    print(86)
elif y == 87:
    print(87)
elif y == 88:
    print(88)
elif y == 89:
    print(89)
elif y == 90:
    print(90)
elif y == 91:
    print(91)
elif y == 92:
    print(92)
elif y == 93:
    print(93)
elif y == 94:
    print(94)
elif y == 95:
    print(95)
elif y == 96:
    print(96)
elif y == 97:
    print(97)
elif y == 98:
    print(98)
elif y == 99:
    print(99)
elif y == 100:
    print(100)
elif y == 101:
    print(101)
elif y == 102:
    print(102)
elif y == 103:
    print(103)
elif y == 104:
    print(104)
elif y == 105:
    print(105)
elif y == 106:
    print(106)
elif y == 107:
    print(107)
elif y == 108:
    print(108)
elif y == 109:
    print(109)
elif y == 110:
    print(110)
elif y == 111:
    print(111)
elif y == 112:
    print(112)
elif y == 113:
    print(113)
elif y == 114:
    print(114)
elif y == 115:
    print(115)
elif y == 116:
    print(116)
elif y == 117:
    print(117)
elif y == 118:
    print(118)
elif y == 119:
    print(119)
elif y == 120:
    print(120)
elif y == 121:
    print(121)
elif y == 122:
    print(122)
elif y == 123:
    print(123)
elif y == 124:
    print(124)
elif y == 125:
    print(125)
elif y == 126:
    print(126)
elif y == 127:
    print(127)
elif y == 128:
    print(128)
elif y == 129:
    print(129)
elif y == 130:
    print(130)
elif y == 131:
    print(131)
elif y == 132:
    print(132)
elif y == 133:
    print(133)
elif y == 134:
    print(134)
elif y == 135:
    print(135)
elif y == 136:
    print(136)
elif y == 137:
    print(137)
elif y == 138:
    print(138)
elif y == 139:
    print(139)
elif y == 140:
    print(140)
elif y == 141:
    print(141)
elif y == 142:
    print(142)
elif y == 143:
    print(143)
elif y == 144:
    print(144)
elif y == 145:
    print(145)
elif y == 146:
    print(146)
elif y == 147:
    print(147)
elif y == 148:
    print(148)
elif y == 149:
    print(149)
elif y == 150:
    print(150)
elif y == 151:
    print(151)
elif y == 152:
    print(152)
elif y == 153:
    print(153)
elif y == 154:
    print(154)
elif y == 155:
    print(155)
elif y == 156:
    print(156)
elif y == 157:
    print(157)
elif y == 158:
    print(158)
elif y == 159:
    print(159)
elif y == 160:
    print(160)
elif y == 161:
    print(161)
elif y == 162:
    print(162)
elif y == 163:
    print(163)
elif y == 164:
    print(164)
elif y == 165:
    print(165)
elif y == 166:
    print(166)
elif y == 167:
    print(167)
elif y == 168:
    print(168)
elif y == 169:
    print(169)
elif y == 170:
    print(170)
elif y == 171:
    print(171)
elif y == 172:
    print(172)
elif y == 173:
    print(173)
elif y == 174:
    print(174)
elif y == 175:
    print(175)
elif y == 176:
    print(176)
elif y == 177:
    print(177)
elif y == 178:
    print(178)
elif y == 179:
    print(179)
elif y == 180:
    print(180)
elif y == 181:
    print(181)
elif y == 182:
    print(182)
elif y == 183:
    print(183)
elif y == 184:
    print(184)
elif y == 185:
    print(185)
elif y == 186:
    print(186)
elif y == 187:
    print(187)
elif y == 188:
    print(188)
elif y == 189:
    print(189)
elif y == 190:
    print(190)
elif y == 191:
    print(191)
elif y == 192:
    print(192)
elif y == 193:
    print(193)
elif y == 194:
    print(194)
elif y == 195:
    print(195)
elif y == 196:
    print(196)
elif y == 197:
    print(197)
elif y == 198:
    print(198)
elif y == 199:
    print(199)
elif y == 200:
    print(200)
elif y == 201:
    print(201)
elif y == 202:
    print(202)
elif y == 203:
    print(203)
elif y == 204:
    print(204)
elif y == 205:
    print(205)
elif y == 206:
    print(206)
elif y == 207:
    print(207)
elif y == 208:
    print(208)
elif y == 209:
    print(209)
elif y == 210:
    print(210)
elif y == 211:
    print(211)
elif y == 212:
    print(212)
elif y == 213:
    print(213)
elif y == 214:
    print(214)
elif y == 215:
    print(215)
elif y == 216:
    print(216)
elif y == 217:
    print(217)
elif y == 218:
    print(218)
elif y == 219:
    print(219)
elif y == 220:
    print(220)
elif y == 221:
    print(221)
elif y == 222:
    print(222)
elif y == 223:
    print(223)
elif y == 224:
    print(224)
elif y == 225:
    print(225)
elif y == 226:
    print(226)
elif y == 227:
    print(227)
elif y == 228:
    print(228)
elif y == 229:
    print(229)
elif y == 230:
    print(230)
elif y == 231:
    print(231)
elif y == 232:
    print(232)
elif y == 233:
    print(233)
elif y == 234:
    print(234)
elif y == 235:
    print(235)
elif y == 236:
    print(236)
elif y == 237:
    print(237)
elif y == 238:
    print(238)
elif y == 239:
    print(239)
elif y == 240:
    print(240)
elif y == 241:
    print(241)
elif y == 242:
    print(242)
elif y == 243:
    print(243)
elif y == 244:
    print(244)
elif y == 245:
    print(245)
elif y == 246:
    print(246)
elif y == 247:
    print(247)
elif y == 248:
    print(248)
elif y == 249:
    print(249)
elif y == 250:
    print(250)
elif y == 251:
    print(251)
elif y == 252:
    print(252)
elif y == 253:
    print(253)
elif y == 254:
    print(254)
elif y == 255:
    print(255)
elif y == 256:
    print(256)
elif y == 257:
    print(257)
elif y == 258:
    print(258)
elif y == 259:
    print(259)
elif y == 260:
    print(260)
elif y == 261:
    print(261)
elif y == 262:
    print(262)
elif y == 263:
    print(263)
elif y == 264:
    print(264)
elif y == 265:
    print(265)
elif y == 266:
    print(266)
elif y == 267:
    print(267)
elif y == 268:
    print(268)
elif y == 269:
    print(269)
elif y == 270:
    print(270)
elif y == 271:
    print(271)
elif y == 272:
    print(272)
elif y == 273:
    print(273)
elif y == 274:
    print(274)
elif y == 275:
    print(275)
elif y == 276:
    print(276)
elif y == 277:
    print(277)
elif y == 278:
    print(278)
elif y == 279:
    print(279)
elif y == 280:
    print(280)
elif y == 281:
    print(281)
elif y == 282:
    print(282)
elif y == 283:
    print(283)
elif y == 284:
    print(284)
elif y == 285:
    print(285)
elif y == 286:
    print(286)
elif y == 287:
    print(287)
elif y == 288:
    print(288)
elif y == 289:
    print(289)
elif y == 290:
    print(290)
elif y == 291:
    print(291)
elif y == 292:
    print(292)
elif y == 293:
    print(293)
elif y == 294:
    print(294)
elif y == 295:
    print(295)
elif y == 296:
    print(296)
elif y == 297:
    print(297)
elif y == 298:
    print(298)
elif y == 299:
    print(299)
if a:
 if a:
  if a:
   if a:
    if a:
     if a:
      if a:
       if a:
        if a:
         if a:
          if a:
           if a:
            if a:
             if a:
              if a:
               if a:
                if a:
                 if a:
                  if a:
                   if a:
                    if a:
                     if a:
                      if a:
                       if a:
                        if a:
                         if a:
                          if a:
                           if a:
                            if a:
                             if a:
                              if a:
                               if a:
                                if a:
                                 if a:
                                  if a:
                                   if a:
                                    if a:
                                     if a:
                                      if a:
                                       if a:
                                        if a:
                                         if a:
                                          if a:
                                           if a:
                                            if a:
                                             if a:
                                              if a:
                                               if a:
                                                if a:
                                                 if a:
                                                  if a:
                                                   if a:
                                                    if a:
                                                     if a:
                                                      if a:
                                                       if a:
                                                        if a:
                                                         if a:
                                                          if a:
                                                           if a:
                                                            if a:
                                                             if a:
                                                              if a:
                                                               if a:
                                                                if a:
                                                                 if a:
                                                                  if a:
                                                                   if a:
                                                                    if a:
                                                                     if a:
                                                                      if a:
                                                                       if a:
                                                                        if a:
                                                                         if a:
                                                                          if a:
                                                                           if a:
                                                                            if a:
                                                                             if a:
                                                                              if a:
                                                                               if a:
                                                                                if a:
                                                                                 if a:
                                                                                  if a:
                                                                                   if a:
                                                                                    if a:
                                                                                     if a:
                                                                                      if a:
                                                                                       if a:
                                                                                        if a:
                                                                                         if a:
                                                                                          if a:
                                                                                           if a:
                                                                                            if a:
                                                                                             if a:
                                                                                              if a:
                                                                                               if a:
                                                                                                if a:
                                                                                                 if a:
                                                                                                  if a:
                                                                                                   print('99 levels')
print(sys.getrecursionlimit())
sys.setrecursionlimit(5000)
print(sys.getrecursionlimit())
sys.setrecursionlimit(True + 9)
print(sys.getrecursionlimit())
sys.setrecursionlimit(0)
print('not reached')
