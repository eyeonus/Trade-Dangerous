#!/bin/bash

####
## Gets the system and station name out of the netLog,
## if verbose logging is enabled.
####

. "${TRADEDIR:-.}/config.sh"

logDir=${FDEVLOGDIR}
if [[ -z "${logDir}" ]]
then
	echo "FDEVLOGDIR not set, aborting."
	exit 1
fi

DATADIR=${TRADEDIR:-.}/data
if [[ ! -d "${DATADIR}" ]]
then
	echo "${DATADIR}: not found, aborting."
	exit 1
fi

checkApp=$(grep -c 'VerboseLogging="1"' "${FDEVLOGDIR}/../AppConfig.xml")
if [[ ${checkApp} -eq 0 ]]
then
	echo "WARNING: VerboseLogging is not enabled."
fi

STNFILE=${DATADIR}/Station.csv
SHIPFILE=${DATADIR}/Ship.csv

# Lists
LIST_Facility=$(echo -en "Black Market\nCommodities\nRefuel\nRepair\nRe-Arm\nOutfitting\nShipyard")

build_ship_list()
{
	local c i j sep OLDIFS
	echo
	echo "Building Ship list..."
	OLDIFS=$IFS
	LIST_Ship=""
	sep=""
	i=0
	while read LINE
	do
		IFS=","
		c=0
		j=0
		for FIELD in $LINE
		do
			FIELD=${FIELD#"'"}
			FIELD=${FIELD%"'"}
			FIELD=${FIELD//"''"/"'"}
			if [[ $i -eq 0 ]]
			then
				FIELD=${FIELD#"unq:"}
				FIELD=${FIELD#"!"}
				if [[ "${FIELD}" = "name" ]]
				then
					c=$j
				fi
			else
				if [[ "$j" -eq "$c" ]]
				then
					LIST_Ship=${LIST_Ship}${sep}${FIELD}
					sep=$'\n'
				fi
			fi
			let j++
		done
		let i++
	done < ${SHIPFILE}
	IFS=$OLDIFS
}

ask_yesno()
{
	local default
	default=$2
	if [[ -z "${default}" ]]
	then
		default="?"
	fi
	case "${default}" in
		[yYjJ]) echo -n "$1 (Y/n): " ;;
		[nN])   echo -n "$1 (y/N): " ;;
		*)      echo -n "$1 (y/n/?): " ;;
	esac
	read antw
	case "${antw:0:1}" in
		[yYjJ]) antw="Y" ;;
		[nN])   antw="N" ;;
		'?')    antw="?" ;;
		*)      antw=${default} ;;
	esac
}

ask_integer()
{
	local default
	default=$2
	if [[ -z "${default}" ]]
	then
		default=0
	fi
	echo -n "$1 (${default}): "
	read antwInt
	if [ "$antwInt" -eq "$antwInt" ] 2> /dev/null
	then
		antwInt=$((10#${antwInt}))
	elif [[ -z "${antwInt}" ]]
	then
		antwInt=${default}
	else
		ask_integer "$1" "${default}"
	fi
}

build_menu()
{
	local e i m add
	OLDIFS=$IFS
	IFS=$'\n'
	i=0;
	unset menuArray
	for m in $2;
	do
		menuArray[$i]=$m
		let i++
	done
	IFS=$OLDIFS
	menuCount=$i

	echo
	echo "Select ${ins} $1"
	for (( i=0; i<${menuCount}; i++ ));
	do
		add=1
		for (( e=0; e<${exclCount}; e++ ));
		do
			if [[ ${exclArray[$e]} -eq $i ]]
			then
				add=0
			fi
		done
		let m=i+1
		if [[ $add -eq 1 ]]
		then
			echo "  ${m}: ${menuArray[$i]}"
		fi
	done

	ask_integer "Choice" "0"
	let antw=${antwInt}-1
	if [[ $antw -lt 0 ]]
	then
		antw=-1
	elif [[ $antw -ge ${menuCount} ]]
	then
		antw=-1
	else
		e=${exclCount}
		exclArray[$e]=$antw
		let exclCount++
	fi
}

ask_menu()
{
	local attrib
	antw=-1
	attrib=$1
	if [[ "$2" = "multi" ]]
	then
		if [[ "$3" = "new" ]]
		then
			unset exclArray
			exclCount=0
		fi
	else
		unset exclArray
		exclCount=0
	fi
	case "$1" in
	Ship)
		build_menu "$1" "${LIST_Ship}"
		;;
	*)
		# Unknown
		;;
	esac
	if [[ ! $antw -lt 0 ]]
	then
		if [[ "$2" = "multi" ]]
		then
			ask_menu "$1" "$2"
		fi
		antw=-1
	fi
}

get_station_fields()
{
	local i OLDIFS
	stnHead=$(head -1 "${STNFILE}")
	OLDIFS=$IFS
	IFS=","
	i=0
	for csvField in ${stnHead}
	do
		csvField=${csvField#"unq:"}
		csvField=${csvField#"!"}
		case "${csvField}" in
			name@System*) CSV_SYS=$i ;;
			name)         CSV_STN=$i ;;
			ls_from_star) CSV_LFS=$i ;;
			blackmarket)  CSV_BLM=$i ;;
			max_pad_size) CSV_PAD=$i ;;
			market)       CSV_COM=$i ;;
			shipyard)     CSV_SHY=$i ;;
			modified)     CSV_MOD=$i ;;
			outfitting)   CSV_OUT=$i ;;
			rearm)        CSV_REA=$i ;;
			refuel)       CSV_REF=$i ;;
			repair)       CSV_REP=$i ;;
		esac
		let i++
	done
	IFS=${OLDIFS}
	colCount=$i

	# default values
	defCol[${CSV_SYS}]=""
	defCol[${CSV_STN}]=""
	defCol[${CSV_LFS}]="0"
	defCol[${CSV_BLM}]="?"
	defCol[${CSV_PAD}]="?"
	defCol[${CSV_COM}]="?"
	defCol[${CSV_SHY}]="?"
	defCol[${CSV_MOD}]="?"
	defCol[${CSV_OUT}]="?"
	defCol[${CSV_REA}]="?"
	defCol[${CSV_REF}]="?"
	defCol[${CSV_REP}]="?"
}

check_system()
{
	# check if system is known
	checkSysName=${sysName//"'"/"''"}
	sysCount=$(grep -c "^'${checkSysName}'" "${DATADIR}/System.csv")
}

check_station()
{
	local i f OLDIFS

	# we need to double the apostroph
	checkSysName=${sysName//"'"/"''"}
	checkPosName=${posName//"'"/"''"}

	# check if station is known
	stnCount=$(grep -c "^'${checkSysName}','${checkPosName}'" "${STNFILE}")
	if [[ ${stnCount} -eq 0 ]]
	then
		# second check with ignore case
		stnCount=$(grep -ic "^'${checkSysName}','${checkPosName}'" "${STNFILE}")
		if [[ ${stnCount} -gt 0 ]]
		then
			stnCount=-1
		fi
	fi
	get_station_fields
	if [[ ${stnCount} -ne 0 ]]
	then
		stnLine=$(grep -i "^'${checkSysName}','${checkPosName}'" "${STNFILE}")
		OLDIFS=$IFS
		IFS=","
		i=0
		for csvField in ${stnLine}
		do
			csvField=${csvField#"'"}
			csvField=${csvField%"'"}
			defCol[$i]=${csvField/"''"/"'"}
			stnCol[$i]=${defCol[$i]}
			let i++
		done
		IFS=${OLDIFS}
	fi
}

output_station_field()
{
	local i
	case "$2" in
		Y) text="Yes" ;;
		N) text="No"  ;;
		S) text="Sml" ;;
		M) text="Med" ;;
		L) text="Lrg" ;;
		*) text="$2"  ;;
	esac
	i=${#outField[@]}
	outField[$i]="$1"
	outText[$i]="$text"
	if [[ ${#outField[$i]} -gt ${max} ]]
	then
		max=${#outField[$i]}
	fi
}

output_station()
{
	local i
	unset outField
	unset outText
	max=0
	output_station_field "System" "${stnCol[${CSV_SYS}]}"
	output_station_field "Station" "${stnCol[${CSV_STN}]}"
	output_station_field "Arrival Point" "${stnCol[${CSV_LFS}]}ls"
	output_station_field "Pad Size" "${stnCol[${CSV_PAD}]}"
	output_station_field "Black Market" "${stnCol[${CSV_BLM}]}"
	output_station_field "Commodities" "${stnCol[${CSV_COM}]}"
	output_station_field "Refuel" "${stnCol[${CSV_REF}]}"
	output_station_field "Repair" "${stnCol[${CSV_REP}]}"
	output_station_field "Re-Arm" "${stnCol[${CSV_REA}]}"
	output_station_field "Outfitting" "${stnCol[${CSV_OUT}]}"
	output_station_field "Shipyard" "${stnCol[${CSV_SHY}]}"

	pad=$(printf '%0.1s' "."{1..30})
	outCount=${#outField[@]}
	for (( i=0; i<${outCount}; i++ ));
	do
		printf '   %s' "${outField[$i]}"
		printf '%*.*s' 0 $((${max} - ${#outField[$i]})) "$pad"
		printf ': %s\n' "${outText[$i]}"
     done

}

# get the last log file
lastLogFile=$(ls -rt "${logDir}"/netLog.* | tail -1)

if [[ -f "${lastLogFile}" ]]
then
	lastLogName=$(basename "${lastLogFile}")
	echo " Log: .../${lastLogName}"

	logLine=$(grep "FindBestIsland:" "${lastLogFile}" | tail -1)
	if [[ ! -z "${logLine}" ]]
	then
		echo "Line: ${logLine}"

		logLine=$(echo "${logLine}" | cut -d" " -f2- )
		OLDIFS=$IFS
		IFS=":"
		i=0
		for checkField in ${logLine}
		do
			logField[$i]=${checkField}
			let i++
		done
		IFS=$OLDIFS
		if [[ $i -gt 3 ]]
		then
			let "sysField = i-1"
			let "posField = i-2"
			posName=${logField[${posField}]}
			sysName=$(echo "${logField[${sysField}]}" | tr [:lower:] [:upper:])
		fi
		if [[ ! -z "${sysName}" ]]
		then
			check_system
			check_station
			stnCol[${CSV_SYS}]=${sysName}
			stnCol[${CSV_STN}]=${posName}

			echo
			echo "     System: ${sysName}"
			echo "   Position: ${posName}"
			if [[ ${stnCount} -ne 0 ]]
			then
				echo
				echo "Station found:"
				output_station

				if [[ "${stnCol[${CSV_SHY}]}" = "Y" ]]
				then
					echo
					cmd="${TRADEPY} shipvendor \
						\"${stnCol[${CSV_SYS}]}/${stnCol[${CSV_STN}]}\""
					eval "${cmd}"
				fi
			fi

			if [[ ${sysCount} -eq 1 ]]
			then
				ins="Station"
				allok="N"
				while [[ ${allok} != "Y" ]]
				do
					echo
					ask_integer "Arrival Point" "${defCol[${CSV_LFS}]}"
					stnCol[${CSV_LFS}]=${antwInt}

					if [[ ${stnCol[${CSV_LFS}]} -lt 0 ]]
					then
						allok="Y"
						echo
						echo "Skipping station data"
					else
						case "${defCol[${CSV_PAD}]}" in
							[sS]) echo -n "Pad Size (S/m/l): " ;;
							[mM]) echo -n "Pad Size (s/M/l): " ;;
							[lL]) echo -n "Pad Size (s/m/L): " ;;
							*)    echo -n "Pad Size (s/m/l/?): " ;;
						esac
						read antw
						case "${antw:0:1}" in
							[sS]) stnCol[${CSV_PAD}]="S" ;;
							[mM]) stnCol[${CSV_PAD}]="M" ;;
							[lL]) stnCol[${CSV_PAD}]="L" ;;
							'?')  stnCol[${CSV_PAD}]="?" ;;
							*)    stnCol[${CSV_PAD}]=${defCol[${CSV_PAD}]} ;;
						esac

						OLDIFS=$IFS
						IFS=$'\n'
						for q in ${LIST_Facility}
						do
							case "$q" in
								'Black Market')	colNum=${CSV_BLM} ;;
								'Commodities')  colNum=${CSV_COM} ;;
								'Shipyard')     colNum=${CSV_SHY} ;;
								'Outfitting')   colNum=${CSV_OUT} ;;
								'Re-Arm')       colNum=${CSV_REA} ;;
								'Refuel')       colNum=${CSV_REF} ;;
								'Repair')       colNum=${CSV_REP} ;;
							esac
							ask_yesno "$q" "${defCol[${colNum}]}"
							stnCol[${colNum}]=$antw
						done
						IFS=$OLDIFS

						echo
						if [[ ${stnCount} -eq 0 ]]
						then
							cmdSwitch="--add"
							echo "Insert Station:"
						else
							cmdSwitch="--update"
							echo "Update Station:"
						fi
						output_station

						echo
						ask_yesno "all OK" "N"
						allok=${antw}
						if [[ ${allok} != "Y" ]]
						then
							for (( i=0; i<${colCount}; i++ ));
							do
								defCol[$i]=${stnCol[$i]}
							done
						fi
					fi
				done

				if [[ ${stnCol[${CSV_LFS}]} -ge 0 ]]
				then
					echo
					cmd="${TRADEPY} station -vv ${cmdSwitch} \
						--ls-from-star=${stnCol[${CSV_LFS}]} \
						--black-market=${stnCol[${CSV_BLM}]} \
						--market=${stnCol[${CSV_COM}]} \
						--shipyard=${stnCol[${CSV_SHY}]} \
						--pad-size=${stnCol[${CSV_PAD}]} \
						--outfitting=${stnCol[${CSV_OUT}]} \
						--rearm=${stnCol[${CSV_REA}]} \
						--refuel=${stnCol[${CSV_REF}]} \
						--repair=${stnCol[${CSV_REP}]} \
						\"${stnCol[${CSV_SYS}]}/${stnCol[${CSV_STN}]}\""
					echo \$ ${cmd}
					eval "${cmd}"
				fi

				dbchange=0
				ins="ShipVendor"
				checkSysName=${stnCol[${CSV_SYS}]//"'"/"''"}
				checkPosName=${stnCol[${CSV_STN}]//"'"/"''"}
				if [[ "${stnCol[${CSV_SHY}]}" = "Y" ]]
				then
					build_ship_list
					ask_menu "Ship" "multi" "new"

					if [[ "${exclCount}" -gt 0 ]]
					then
						echo
						echo "Writing Ships to database ..."

						for (( i=0; i<${menuCount}; i++ ));
						do
							add=0
							for (( e=0; e<${exclCount}; e++ ));
							do
								if [[ ${exclArray[$e]} -eq $i ]]
								then
									add=1
								fi
							done

							checkShipName=${menuArray[$i]//"'"/"''"}
							shipCount=$(grep -c "^'${checkSysName}','${checkPosName}','${checkShipName}'" "${DATADIR}/${ins}.csv")

							if [[ $add -eq 1 ]]
							then
								cmdSwitch="--add"
								let "doit=(shipCount==0)"
							else
								cmdSwitch="--remove"
								let "doit=(shipCount==1)"
							fi

							if [[ ${doit} -eq 1 ]]
							then
								dbchange=1
								echo "${cmdSwitch:2:3}: ${menuArray[$i]}"
								cmd="${TRADEPY} shipvendor ${cmdSwitch} \
									--no-export \
									\"${stnCol[${CSV_SYS}]}/${stnCol[${CSV_STN}]}\" \
									\"${menuArray[$i]}\""
								eval "${cmd}" 2>&1 > /dev/null
							fi
						done
					else
						echo "No ships selected."
					fi
				elif [[ "${stnCol[${CSV_SHY}]}" = "N" ]]
				then
					shipCount=$(grep -c "^'${checkSysName}','${checkPosName}'" "${DATADIR}/${ins}.csv")
					if [[ ${shipCount} -gt 0 ]]
					then
						echo
						echo "There are ships for this station in the database."
						ask_yesno "Delete them" "N"
						if [[ "${antw}" = "Y" ]]
						then
							build_ship_list
							OLDIFS=$IFS
							IFS=$'\n'
							i=0;
							unset shipArray
							for m in ${LIST_Ship};
							do
								shipArray[$i]=$m
								let i++
							done
							IFS=$OLDIFS
							shipCount=$i
							for (( i=0; i<${shipCount}; i++ ));
							do
								add=0
								checkShipName=${shipArray[$i]//"'"/"''"}
								dbCount=$(grep -c "^'${checkSysName}','${checkPosName}','${checkShipName}'" "${DATADIR}/${ins}.csv")
								cmdSwitch="--remove"
								if [[ ${dbCount} -gt 0 ]]
								then
									dbchange=1
									echo "${cmdSwitch:2:3}: ${shipArray[$i]}"
									cmd="${TRADEPY} shipvendor ${cmdSwitch} \
										--no-export \
										\"${stnCol[${CSV_SYS}]}/${stnCol[${CSV_STN}]}\" \
										\"${shipArray[$i]}\""
									eval "${cmd}" 2>&1 > /dev/null
								fi
							done
						fi
					fi
				fi
				if [[ ${dbchange} -eq 1 ]]
				then
					cmd="${TRADEPY} export --table ${ins}"
					eval "${cmd}"
				fi
				if [[ "${stnCol[${CSV_SHY}]}" = "Y" ]]
				then
					echo
					cmd="${TRADEPY} shipvendor \
						\"${stnCol[${CSV_SYS}]}/${stnCol[${CSV_STN}]}\""
					echo \$ ${cmd}
					eval "${cmd}"
				fi
			else
				echo "Unknown System!"
			fi
		else
			echo "Systemname not found!"
		fi
	else
		echo "Positiondata not found!"
	fi
else
	echo "Logfile not found!"
fi
