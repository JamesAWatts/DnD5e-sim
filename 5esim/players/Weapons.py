bonus = 0

weapons_list = {'melee weapons': {
                    'unarmed':{
                        'attack_range':int(1),
                        'die':int(4),
                        'on_hit_effect': 'swift',
                        'bonus':int(bonus + 0)
                        }, 
                    'dagger':{
                        'attack_range':int(1),
                        'die':int(6), 
                        'on_hit_effect': 'swift', 
                        'bonus':int(bonus + 0)
                        }, 
                    'staff':{
                        'attack_range':int(1), 
                        'die':int(6), 
                        'on_hit_effect': 'vex', 
                        'bonus':int(bonus + 0)
                        },
                    'hammer':{
                        'attack_range':int(1), 
                        'die':int(6), 
                        'on_hit_effect': 'slow', 
                        'bonus':int(bonus + 0)
                        },
                    'sword':{
                        'attack_range':int(1), 
                        'die':int(8), 
                        'on_hit_effect':'vex', 
                        'bonus':int(bonus + 0)
                        },
                    'axe':{
                        'attack_range':int(1), 
                        'die':int(8), 
                        'on_hit_effect':'graze', 
                        'bonus':int(bonus + 0)
                        },
                    'mace':{
                        'attack_range':int(1), 
                        'die':int(8), 
                        'on_hit_effect':'sap', 
                        'bonus':int(bonus + 0)
                        },
                    'warhammer':{
                        'attack_range':int(1), 
                        'die':int(8), 
                        'on_hit_effect':'push', 
                        'bonus':int(bonus + 0)
                        },
                    'greatsword':{
                        'attack_range':int(1), 
                        'die':int(10), 
                        'on_hit_effect':'graze', 
                        'bonus':int(bonus + 0)
                        },
                    'whip':{
                        'attack_range':int(2), 
                        'die':int(6), 
                        'on_hit_effect':'slow', 
                        'bonus':int(bonus + 0)
                        },
                    'maul':{
                        'attack_range':int(2), 
                        'die':int(10), 
                        'on_hit_effect':'push', 
                        'bonus':int(bonus + 0)
                        },
                    'glaive':{
                        'attack_range':int(2), 
                        'die':int(10), 
                        'on_hit_effect':'cleave',
                        'bonus':int(bonus + 0)
                        }
                    },
                'ranged weapons': {
                    'sling':{
                        'attack_range':int(3), 
                        'die':int(4), 
                        'on_hit_effect':'slow', 
                        'bonus':int(bonus + 0)
                        },
                    'shortbow':{
                        'attack_range':int(4), 
                        'die': int(6), 
                        'on_hit_effect':'swift', 
                        'bonus':int(bonus + 0)
                        },
                    'bow':{
                        'attack_range':int(5), 
                        'die': int(6), 
                        'on_hit_effect':'sap', 
                        'bonus':int(bonus + 0)
                        },
                    'longbow' :{
                        'attack_range':int(7), 
                        'die':int(8), 
                        'on_hit_effect':'vex', 
                        'bonus':int(bonus + 0)
                        },
                    'crossbow':{
                        'attack_range':int(5), 
                        'die':int(10), 
                        'on_hit_effect':'push', 
                        'bonus':int(bonus + 0)
                        }
                    },
                'cantrips': {
                    'fire_bolt':{
                        'attack_range':int(5), 
                        'die':int(10), 
                        'on_hit_effect':'graze', 
                        'bonus':int(bonus + 0)
                        },
                    'frost_bolt':{
                        'attack_range':int(5), 
                        'die':int(6), 
                        'on_hit_effect':'slow', 
                        'bonus':int(bonus + 0)
                        },
                    'static_bolt':{
                        'attack_range':int(5), 
                        'die':int(6), 
                        'on_hit_effect':'sap', 
                        'bonus':int(bonus + 0)
                        },
                    'poison_spray':{
                        'attack_range':int(3),
                        'die':int(8),
                        'on_hit_effect':'cleave',
                        'bonus':int(bonus + 0)
                        },
                    'thorn_whip':{
                        'attack_range':int(2), 
                        'die':int(10), 
                        'on_hit_effect':'slow', 
                        'bonus':int(bonus + 0)
                        },
                    'rock_slam':{
                        'attack_range':int(3), 
                        'die':int(8), 
                        'on_hit_effect':'push', 
                        'bonus':int(bonus + 0)
                        }
                    }
               }